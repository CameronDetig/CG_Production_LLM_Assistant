# Repository Guidelines

## Project Structure & Module Organization

`backend/lambda_function.py` handles API requests. Backend code is divided into `src/core/` for agent logic, `src/services/` for database/model/storage integrations, and `src/auth/` for Cognito authentication. `backend/testing/` holds diagnostics and a local Flask server; `backend/scripts/` and `backend/docs/` cover deployment.

`frontend_gradio/app.py` implements the web UI. `frontend_blender/` contains the Blender add-on, including operators, panels, properties, and API client. `.github/workflows/` contains backend deployment and Hugging Face synchronization workflows.

## Build, Test, and Development Commands

`infra/` owns the assistant's production AWS resources and reads shared identifiers from SSM. See `infra/README.md` for import/bootstrap steps. Do not use retired direct deployment scripts or depend on the parent repository for releases.

Use separate virtual environments as needed and run commands from the indicated directory:

- `backend/` or `frontend_gradio/`: `python -m pip install -r requirements.txt` installs component dependencies.
- `backend/`: `python testing/test_local.py` exercises database and backend integrations using configured services.
- `backend/`: install Flask with `python -m pip install flask`, then run `python testing/lambda_server.py` to serve the local API on port 5000.
- `frontend_gradio/`: `python app.py` starts Gradio. For the local backend, set `API_ENDPOINT=http://localhost:5000` without `/chat`; the client appends route paths.
- `backend/`: `docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t cg-chatbot .` builds the backend container.

Install the Blender add-on using `frontend_blender/README.md` and verify it inside Blender.

## Coding Style & Naming Conventions

Use four spaces, `snake_case` functions/modules, `PascalCase` classes, and uppercase constants. Preserve existing type hints and Blender registration conventions. Keep service integrations out of UI modules where practical. No shared formatter or linter configuration is checked in.

## Testing Guidelines

Backend checks are standalone integration scripts; no enforced coverage threshold exists. Add focused `test_*.py` regressions under `backend/testing/`, mocking external services for isolated checks. Validate authentication, streamed responses, search results, and conversation behavior when affected. Manually verify UI changes in Gradio or Blender and include screenshots. Report unavailable service/model prerequisites and skipped checks.

## Commit & Pull Request Guidelines

History uses descriptive subjects without mandatory prefixes. Explain behavior changes, affected clients, configuration changes, and validation in PRs. Commit here and publish the commit before updating the parent submodule reference. Changes to `frontend_gradio/**` pushed to `main` trigger Hugging Face synchronization; backend changes create a Terraform release plan, and a separate manual approval workflow applies it.

## Security & Compatibility

Keep secrets and `lambda_config.json` untracked. Preserve read-only restrictions on LLM-generated SQL. Coordinate database fields and embedding dimensions with the metadata extractor. Treat current code and configuration as authoritative where older README model names or paths disagree.
