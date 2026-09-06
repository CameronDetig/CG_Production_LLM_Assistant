import unittest
from release import object_key, plan_changes, validate_run, validate_manifest


class ReleaseSafetyTests(unittest.TestCase):
    def test_destructive_change_rejected(self):
        for actions in [['delete'], ['delete', 'create'], ['create', 'delete']]:
            with self.assertRaises(ValueError):
                plan_changes({'resource_changes': [{'address': 'aws_db_instance.db', 'change': {'actions': actions}}]})

    def test_adoption_rejects_effective_change(self):
        plan = {'resource_changes': [{'address': 'aws_lambda_function.app', 'change': {
            'actions': ['update'], 'before': {'timeout': 180}, 'after': {'timeout': 120}}}]}
        with self.assertRaises(ValueError):
            plan_changes(plan, adoption=True)
        self.assertEqual(len(plan_changes(plan)), 1)

    def test_sensitivity_only_import_difference(self):
        plan = {'resource_changes': [{'address': 'aws_lambda_function.app', 'change': {
            'actions': ['update'], 'before': {'environment': 'same'}, 'after': {'environment': 'same'}}}]}
        self.assertEqual(plan_changes(plan, adoption=True), [])

    def test_untrusted_run_rejected(self):
        config = {'workflow': '.github/workflows/release.yml', 'repository': 'owner/repo'}
        run = {'conclusion': 'success', 'head_branch': 'main', 'event': 'push',
               'path': config['workflow'], 'repository': {'full_name': config['repository']}}
        validate_run(run, config)
        for key, value in [('event', 'pull_request'), ('head_branch', 'feature'),
                           ('conclusion', 'failure'), ('path', '.github/workflows/other.yml')]:
            with self.assertRaises(ValueError):
                validate_run(dict(run, **{key: value}), config)

    def test_run_key_rejects_path_injection(self):
        with self.assertRaises(ValueError):
            object_key('../state', 1, 'release.tfplan')

    def test_unknown_values_are_not_a_clean_adoption(self):
        plan = {'resource_changes': [{'address': 'aws_lambda_function.app', 'change': {
            'actions': ['update'], 'before': {'x': None}, 'after': {'x': None}, 'after_unknown': {'x': True}}}]}
        with self.assertRaises(ValueError):
            plan_changes(plan, adoption=True)

    def test_expired_or_wrong_commit_plan_rejected(self):
        manifest = {'commit': 'abc', 'repository': 'owner/repo', 'created_at': 100}
        run = {'head_sha': 'abc'}
        config = {'repository': 'owner/repo'}
        validate_manifest(manifest, run, config, 101)
        for now in [99, 86500]:
            with self.assertRaises(ValueError):
                validate_manifest(manifest, run, config, now)
        with self.assertRaises(ValueError):
            validate_manifest(manifest, {'head_sha': 'other'}, config, 101)


if __name__ == '__main__':
    unittest.main()
