# Testing

All tests live in the top-level `tests/` folder, in a subfolder per component. Run every command from the repository root unless noted.

| Folder | Covers | Framework | Needs live services | Runs in CI |
|---|---|---|---|---|
| `tests/backend/` | Streaming helpers, Cognito token validation, warmup | `unittest` and plain asserts | No (mocked) | Yes, `backend-checks.yml` `test` job |
| `tests/backend/integration/` | Full Lambda handler against a real database, Bedrock and Cognito | Scripts | **Yes** (needs `backend/.env`) | No |
| `tests/frontend_web/` | SSE parsing, Cognito session and PKCE | vitest | No | Yes, `deploy-frontend.yml` `verify` job |
| `tests/frontend_blender/` | Blender add-on HTTP client (mocked HTTP) | `unittest` | No | Yes, `backend-checks.yml` `test` job |
| `tests/infra/` | Release tooling in `infra/tools/` (`release.py`) | `unittest` | No | Yes, `infra-checks.yml` and `deploy-backend.yml` |

`backend/testing/` is not a test folder: it holds the local Flask server (`lambda_server.py`) and a sample payload.

## Running

```sh
# Backend (mocked). Needs boto3, python-jose[cryptography] and requests.
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_*.py'
PYTHONPATH=backend python tests/backend/test_warmup.py

# Backend integration (live services; see backend/README.md for configuration)
python tests/backend/integration/test_local.py
python tests/backend/integration/test_chat.py

# Blender client
python -m unittest discover -s tests/frontend_blender -p 'test_*.py'

# Release tooling
python -m unittest discover -s tests/infra -p 'test_*.py'

# Web frontend (run in frontend_web/)
npm test
npm run lint
npm run build   # also type-checks the tests
```

## Conventions

- Put a test under the component it covers. Mock external services; anything that needs a live service goes in `integration/`.
- Backend unit tests import code from `backend/` through `PYTHONPATH=backend`. The `warmup`, integration and infra tests also add the path themselves so they run directly.
- Blender tests import `api_client` directly and must not import the add-on package, which needs `bpy` and only exists inside Blender.
- Web frontend tests sit outside the `frontend_web/` package. `frontend_web/vite.config.ts` points vitest at `tests/frontend_web/` and resolves their package imports from `frontend_web/node_modules`; `tsconfig.app.json` includes the folder so `npm run build` type-checks them. Import app code with relative paths such as `../../frontend_web/src/auth`.
- Add new dependencies to the component's own manifest, not to `tests/`. CI installs only what each job needs.
