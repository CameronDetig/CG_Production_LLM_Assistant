"""Write the API's OpenAPI schema to docs/openapi.json.

Run from the repo root after changing a route or request/response model in api_app.py:

    python backend/scripts/export_openapi.py

Needs fastapi, boto3 and python-jose installed. No AWS access is required: the schema is
built from the route definitions and nothing is called.
"""

import json
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(os.path.dirname(BACKEND_DIR), "docs", "openapi.json")

sys.path.insert(0, BACKEND_DIR)
# boto3 clients are created at import time but never called here. Placeholder values keep
# that import from depending on the local AWS profile or its credential provider.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "unused")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "unused")

from api_app import app  # noqa: E402


def main() -> None:
    with open(OUTPUT_PATH, "w") as output:
        json.dump(app.openapi(), output, indent=2)
        output.write("\n")
    print(f"Wrote {os.path.relpath(OUTPUT_PATH)}")


if __name__ == "__main__":
    main()
