# Testing

All tests live in the top-level `tests/` folder, in a subfolder per component. Run every command from the repository root unless noted.

| Folder | Covers | Framework | Needs live services | Runs in CI |
|---|---|---|---|---|
| `tests/backend/` | API routes and chat stream (`api_app.py` via FastAPI `TestClient`), streaming helpers, Cognito token validation, warmup, search filter SQL rewriting | `unittest` and plain asserts | No (mocked) | Yes, `backend-checks.yml` `test` job |
| `tests/backend/integration/` | Service connectivity, and one chat through `api_app.py` against the real database, DynamoDB, embeddings and Bedrock (auth bypassed) | Scripts | **Yes** (needs `backend/.env`) | No |
| `tests/frontend_web/` | SSE parsing, Cognito session and PKCE, search filter menu | vitest | No | Yes, `deploy-frontend.yml` `verify` job |
| `tests/smoke/` | Post-deploy checks of the live site, plus unit tests of the check logic | `unittest` (script uses `urllib`) | Live site only, no credentials | Unit tests in `backend-checks.yml`; the script runs after every release (see below) |
| `tests/frontend_blender/` | Blender add-on HTTP client (mocked HTTP) | `unittest` | No | Yes, `backend-checks.yml` `test` job |
| `tests/infra/` | Release tooling in `infra/tools/` (`release.py`) | `unittest` | No | Yes, `infra-checks.yml` and `deploy-backend.yml` |

To run the API itself locally, see "Local server" in `backend/README.md`.

## Running

```sh
# Backend (mocked). Needs boto3, python-jose[cryptography], requests, sqlglot, fastapi and httpx.
python -m unittest discover -s tests/backend -p 'test_*.py'
python tests/backend/test_warmup.py

# Backend integration (live services; see backend/README.md for configuration)
python tests/backend/integration/test_local.py
python tests/backend/integration/test_chat.py

# Blender client
python -m unittest discover -s tests/frontend_blender -p 'test_*.py'

# Smoke script unit tests, then the real thing against a deployed site
python -m unittest discover -s tests/smoke -p 'test_*.py'
python tests/smoke/smoke.py https://<cloudfront-domain>

# Release tooling
python -m unittest discover -s tests/infra -p 'test_*.py'

# Web frontend (run in frontend_web/)
npm test
npm run lint
npm run build   # also type-checks the tests
```

## Conventions

- Put a test under the component it covers. Mock external services; anything that needs a live service goes in `integration/`.
- Backend tests add `backend/` to `sys.path` themselves, so they run with plain `python`. The repo-root `pyrightconfig.json` tells the editor where `src` lives.
- Blender tests import `api_client` directly and must not import the add-on package, which needs `bpy` and only exists inside Blender.
- Web frontend tests sit outside the `frontend_web/` package. `frontend_web/vite.config.ts` points vitest at `tests/frontend_web/` and resolves their package imports from `frontend_web/node_modules`; `tsconfig.app.json` includes the folder so `npm run build` type-checks them, and its `paths` entry maps the packages the tests import (`vitest`, `@testing-library/*`, `react`) back into `frontend_web/node_modules`. A test that imports another package needs a `paths` entry too. Import app code with relative paths such as `../../frontend_web/src/auth`.
- Add new dependencies to the component's own manifest, not to `tests/`. CI installs only what each job needs.

## Smoke tests

`tests/smoke/smoke.py` checks the **live** site over HTTPS with the standard library only, so it needs no credentials. It runs once per release, at the end of the last job that ran in `approve-release.yml`:

- when the frontend is deployed (with or without a backend apply), in the `frontend` job, using the CloudFront domain found by name;
- for a backend-only release ("deploy frontend" unticked), in the `apply` job, using `terraform output frontend_url`.

The checks go through the whole stack, so one run after the final change covers both halves. If the `frontend` job fails before deploying (for example, the newest build has not succeeded), no smoke test runs, but the run is red anyway.

Checks (each retried up to 6 times, 10 seconds apart, because CloudFront invalidation and Lambda cold starts take a moment):

1. `GET /` returns 200 and the app shell (`#root`).
2. `GET /config.json` returns 200 with non-empty `cognitoDomain` and `cognitoClientId`. The copy in the repo is an empty placeholder; Terraform generates the real one.
3. `GET /api/health` returns 200 `{"status":"ok"}`, which proves CloudFront to API Gateway to Lambda.
4. Anonymous `GET /api/conversations` returns 401, which proves the JWT authorizer is attached.

A failure turns the release run red but **does not roll back**; the apply or deploy has already happened. Investigate, then fix forward or redeploy a previous plan or frontend build. Tune with `SMOKE_ATTEMPTS` and `SMOKE_DELAY_SECONDS`. If Python on your machine cannot verify certificates (a common macOS python.org install), point `SSL_CERT_FILE` at a CA bundle such as `/etc/ssl/cert.pem`; do not disable verification.

Not covered yet: an authenticated end-to-end check (sign in, send a chat). It needs a dedicated Cognito test user and a stored secret.
