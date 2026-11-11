# Repository Guidelines

## Project Structure & Module Organization

`backend/api_app.py` is the FastAPI app that serves every API route; in production the container runs it with uvicorn behind the AWS Lambda Web Adapter (see `backend/Dockerfile`), so there is no Lambda handler function. Backend code is divided into `src/core/` for agent logic, `src/services/` for database/model/storage integrations, and `src/auth/` for Cognito authentication. All tests live under the top-level `tests/` folder, one subfolder per component (`backend/`, `frontend_web/`, `frontend_blender/`, `infra/`); `backend/scripts/` and `backend/docs/` cover deployment. Cross-cutting documentation lives in the top-level `docs/` (start at `docs/README.md`); components may have their own `docs/` folder. `specs/` is a local, git-ignored folder of work specs and is not documentation.

`frontend_web/` implements the browser web UI. `frontend_blender/` contains the Blender add-on, including operators, panels, properties, and API client. `.github/workflows/` contains backend and web frontend deployment workflows.

## Build, Test, and Development Commands

`infra/` owns the assistant's production AWS resources and reads shared identifiers from SSM. See `infra/README.md` for import/bootstrap steps. Do not use retired direct deployment scripts or depend on the parent repository for releases.

Use separate virtual environments as needed and run commands from the indicated directory:

- `backend/`: `python -m pip install -r requirements.txt` installs component dependencies.
- Repo root: `PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_*.py'` runs the mocked backend tests; `python tests/backend/integration/test_local.py` exercises database and backend integrations using configured services. See `docs/testing.md` for every suite.
- `backend/`: `uvicorn api_app:app --reload --port 8080` serves the same API locally (port 8080 matches the container).
- `backend/`: `docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t cg-chatbot .` builds the backend container.

Install the Blender add-on using `frontend_blender/README.md` and verify it inside Blender.

## Coding Style & Naming Conventions

Use four spaces, `snake_case` functions/modules, `PascalCase` classes, and uppercase constants. Preserve existing type hints and Blender registration conventions. Keep service integrations out of UI modules where practical. No shared formatter or linter configuration is checked in.

## Testing Guidelines

No enforced coverage threshold exists. Put tests in the top-level `tests/` folder under the component they cover, not next to the source. Add focused `test_*.py` regressions under `tests/backend/`, mocking external services for isolated checks; scripts that need live services go in `tests/backend/integration/`. Frontend tests go in `tests/frontend_web/` (vitest), Blender client tests in `tests/frontend_blender/`, and release-tooling tests in `tests/infra/`. Validate authentication, streamed responses, search results, and conversation behavior when affected. Manually verify UI changes in the web frontend or Blender and include screenshots. Report unavailable service/model prerequisites and skipped checks.

## Documentation

After implementing a significant change (new or changed workflow, infrastructure, deployment or release behavior, API or data contract, configuration, or test layout), update or add the relevant docs in the same commit. Cross-cutting topics go in the top-level `docs/` (add new files to the index in `docs/README.md`); component-specific topics go in that component's `docs/` folder. Remove or correct statements the change makes untrue, such as the "Known gaps" list in `docs/ci-cd.md`. Small fixes that do not change behavior do not need doc updates.

## Commit & Pull Request Guidelines

History uses descriptive subjects without mandatory prefixes. Explain behavior changes, affected clients, configuration changes, and validation in PRs. Commit here and publish the commit before updating the parent submodule reference. Changes to `frontend_web/**` pushed to `main` build and verify the web frontend, and a separate manual approval workflow deploys that build; backend changes create a Terraform release plan, and a separate manual approval workflow applies it.

## Security & Compatibility

Keep secrets and `lambda_config.json` untracked. Preserve read-only restrictions on LLM-generated SQL. Coordinate database fields and embedding dimensions with the metadata extractor. Treat current code and configuration as authoritative where older README model names or paths disagree.
