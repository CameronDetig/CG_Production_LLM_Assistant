"""Checks for the show / asset-type search filters (pure SQL rewriting, no database).

Run from the repo root:  python -m unittest discover -s tests/backend -p 'test_*.py'
Needs sqlglot.
"""

import os
import sys
import unittest

# The code under test lives in backend/; make `src` importable without needing PYTHONPATH.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

import sqlglot  # noqa: E402
from sqlglot import exp  # noqa: E402

from src.services.search_filters import (  # noqa: E402
    apply_search_filters,
    describe_filters,
    has_filters,
    normalize_filters,
)

SPRING = {"shows": ["spring"], "file_types": []}
SPRING_IMAGES = {"shows": ["spring"], "file_types": ["image"]}

FILES_CTE = (
    "files AS NOT MATERIALIZED "
    "(SELECT * FROM files WHERE show IN ('spring') AND file_type IN ('image'))"
)
IMAGES_CTE = (
    "images AS NOT MATERIALIZED "
    "(SELECT * FROM images WHERE file_id IN (SELECT id FROM files))"
)
SHOWS_CTE = "shows AS NOT MATERIALIZED (SELECT * FROM shows WHERE name IN ('spring'))"
CHILD_TABLES = [
    "blend_files", "images", "videos", "audio", "code",
    "spreadsheets", "documents", "caches", "unknown_files",
]


def cte_names(sql):
    """Names defined by the first WITH clause of the statement, in order."""
    tree = sqlglot.parse_one(sql, dialect="postgres")
    return [cte.alias for cte in tree.args["with"].expressions]


class NormalizeFiltersTest(unittest.TestCase):
    def test_missing_filters_mean_no_restriction(self):
        self.assertEqual(normalize_filters(None), {"shows": [], "file_types": []})
        self.assertFalse(has_filters(None))
        self.assertFalse(has_filters({"shows": [], "file_types": []}))

    def test_values_are_stripped_and_deduplicated(self):
        result = normalize_filters({"shows": [" spring ", "spring", "", 7, "charge"], "file_types": None})
        self.assertEqual(result, {"shows": ["spring", "charge"], "file_types": []})
        self.assertTrue(has_filters(result))

    def test_description_names_the_selection(self):
        self.assertEqual(describe_filters(None), "")
        text = describe_filters({"shows": ["spring"], "file_types": ["image", "blend"]})
        self.assertIn("shows: spring", text)
        self.assertIn("file types: image, blend", text)


class ApplySearchFiltersTest(unittest.TestCase):
    def test_no_filters_returns_sql_unchanged(self):
        sql = "select  *  from files"
        self.assertEqual(apply_search_filters(sql, None), sql)
        self.assertEqual(apply_search_filters(sql, {"shows": [], "file_types": []}), sql)

    def test_every_guarded_table_is_shadowed_by_a_filtered_cte(self):
        result = apply_search_filters("SELECT COUNT(*) FROM files", SPRING_IMAGES)
        self.assertTrue(result.startswith(f"WITH {FILES_CTE}, "))
        self.assertIn(IMAGES_CTE, result)
        self.assertIn(SHOWS_CTE, result)
        # files must come first: the child CTEs read the filtered files CTE defined before them.
        self.assertEqual(cte_names(result), ["files", *CHILD_TABLES, "shows"])

    def test_original_sql_is_kept_verbatim(self):
        # sqlglot would regenerate pgvector's <=> as IS NOT DISTINCT FROM, so the query text
        # must be spliced, never re-serialized.
        sql = (
            "SELECT f.file_name, img.thumbnail_path\nFROM files f JOIN images img ON f.id = img.file_id\n"
            "WHERE img.visual_embedding IS NOT NULL\n"
            "ORDER BY img.visual_embedding <=> '[0.1,0.2]'::vector LIMIT 10"
        )
        result = apply_search_filters(sql, SPRING_IMAGES)
        self.assertTrue(result.endswith(" " + sql))
        self.assertNotIn("DISTINCT", result)

    def test_only_file_type_filter_leaves_shows_table_alone(self):
        result = apply_search_filters("SELECT * FROM files", {"file_types": ["blend", "video"]})
        self.assertIn(
            "files AS NOT MATERIALIZED (SELECT * FROM files WHERE file_type IN ('blend', 'video'))",
            result,
        )
        self.assertEqual(cte_names(result), ["files", *CHILD_TABLES])

    def test_only_show_filter(self):
        result = apply_search_filters("SELECT name FROM shows", SPRING)
        self.assertIn("files AS NOT MATERIALIZED (SELECT * FROM files WHERE show IN ('spring'))", result)
        self.assertIn(SHOWS_CTE, result)

    def test_top_level_union_gets_one_with_clause(self):
        sql = "SELECT id FROM files WHERE file_type = 'image' UNION SELECT file_id FROM videos"
        result = apply_search_filters(sql, SPRING)
        self.assertTrue(result.endswith(" " + sql))
        self.assertIsInstance(sqlglot.parse_one(result, dialect="postgres"), exp.Union)

    def test_filter_ctes_are_merged_into_an_existing_with_clause(self):
        result = apply_search_filters(
            "WITH recent AS (SELECT * FROM files ORDER BY modified_date DESC LIMIT 10) "
            "SELECT * FROM recent",
            SPRING,
        )
        self.assertEqual(result.count("WITH "), 1)
        self.assertEqual(cte_names(result), ["files", *CHILD_TABLES, "shows", "recent"])
        self.assertTrue(
            result.endswith(
                ", recent AS (SELECT * FROM files ORDER BY modified_date DESC LIMIT 10) SELECT * FROM recent"
            )
        )

    def test_existing_with_clause_after_comments_and_in_lowercase(self):
        result = apply_search_filters(
            "-- newest first\n/* top ten */ with recent as (select * from files) select * from recent",
            SPRING,
        )
        self.assertTrue(result.startswith("-- newest first\n/* top ten */ WITH files AS NOT MATERIALIZED"))
        self.assertEqual(cte_names(result)[-1], "recent")

    def test_column_named_like_a_keyword_prefix_is_not_mistaken_for_with(self):
        sql = "SELECT width FROM images"
        self.assertTrue(apply_search_filters(sql, SPRING).endswith(" " + sql))

    def test_cte_named_after_a_table_is_rejected(self):
        # It would either collide with the filter CTE or, nested, be confusing to reason about.
        for sql in (
            "WITH files AS (SELECT * FROM files) SELECT * FROM files",
            "SELECT * FROM files WHERE id IN (WITH images AS (SELECT 1 AS file_id) SELECT file_id FROM images)",
        ):
            with self.assertRaisesRegex(ValueError, "do not name a CTE"):
                apply_search_filters(sql, SPRING)

    def test_schema_qualified_table_is_rejected(self):
        # public.files would read the real table and skip the CTE of the same name.
        for sql in ("SELECT * FROM public.files", "SELECT * FROM files f JOIN Public.Images i ON f.id = i.file_id"):
            with self.assertRaisesRegex(ValueError, "without a schema prefix"):
                apply_search_filters(sql, SPRING)

    def test_recursive_with_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "WITH RECURSIVE"):
            apply_search_filters(
                "WITH RECURSIVE n AS (SELECT 1 AS i UNION ALL SELECT i + 1 FROM n WHERE i < 3) SELECT * FROM n",
                SPRING,
            )

    def test_unrelated_schema_qualified_tables_and_ctes_are_allowed(self):
        sql = "WITH totals AS (SELECT COUNT(*) AS n FROM files) SELECT n FROM totals, pg_catalog.pg_class LIMIT 1"
        self.assertEqual(cte_names(apply_search_filters(sql, SPRING))[-1], "totals")

    def test_quotes_in_values_are_escaped(self):
        hostile = "x') OR 1=1 --"
        result = apply_search_filters("SELECT * FROM files", {"shows": [hostile]})
        self.assertIn("show IN ('x'') OR 1=1 --')", result)
        tree = sqlglot.parse_one(result, dialect="postgres")
        self.assertEqual({node.this for node in tree.find_all(exp.Literal)}, {hostile})

    def test_result_is_a_single_statement(self):
        result = apply_search_filters(
            "SELECT f.show, COUNT(*) FROM files f GROUP BY f.show ORDER BY 2 DESC LIMIT 5",
            SPRING_IMAGES,
        )
        statements = sqlglot.parse(result, dialect="postgres")
        self.assertEqual(len(statements), 1)
        self.assertIsInstance(statements[0], exp.Select)
        self.assertTrue(result.endswith("LIMIT 5"))


if __name__ == "__main__":
    unittest.main()
