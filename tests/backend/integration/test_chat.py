"""
End-to-end chat check against live services.
Sends one query through the deployed FastAPI app (backend/api_app.py) in-process and prints the
SSE stream. Uses the real database, DynamoDB conversation table, embeddings and Bedrock from
backend/.env; only Cognito sign-in is skipped by overriding the auth dependency.

Usage (from the repo root):  python tests/backend/integration/test_chat.py ["your query"]
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from backend/.env
# (this file lives in tests/backend/integration/)
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'backend')
load_dotenv(os.path.join(backend_dir, '.env'))

# Add backend directory to path
sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient  # noqa: E402

from api_app import app, authenticated_user  # noqa: E402


def test_chat_query(query_text="Show me the most recent images from the spring show", user_id="test_user"):
    """Stream one chat request and print each SSE event as it arrives."""
    app.dependency_overrides[authenticated_user] = lambda: user_id

    print("=" * 80)
    print("Testing Chat Query")
    print("=" * 80)
    print(f"Query: {query_text}")
    print(f"User:  {user_id}")
    print("-" * 80)
    print("Response:")

    try:
        with TestClient(app) as client:
            with client.stream("POST", "/api/chat", json={"query": query_text}) as response:
                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    print(response.read().decode())
                    return
                for chunk in response.iter_text():
                    print(chunk, end='', flush=True)
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        app.dependency_overrides.clear()

    print("\n" + "=" * 80)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        test_chat_query(" ".join(sys.argv[1:]))
    else:
        test_chat_query()
