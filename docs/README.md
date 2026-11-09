# Documentation

Cross-cutting documentation for the whole repository lives here. Component-specific docs live next to the component.

| Location | What goes there |
|---|---|
| `docs/` | Cross-cutting docs: CI/CD, testing, release process |
| `backend/docs/` | Backend setup and deployment notes (S3, database, DynamoDB, Cognito, image) |
| `<component>/docs/` | Any other component may add its own `docs/` folder |
| `specs/` | Local, git-ignored work specs used to plan and step through changes. Not documentation. |

## Index

- [testing.md](testing.md): where each component's tests live, how to run them, and which ones run in CI.
- [ci-cd.md](ci-cd.md): GitHub Actions workflows, the two-stage backend release, AWS roles, and constraints to keep in mind when changing them.

## Conventions

- Put a doc update in the same commit as the change it describes.
- Prefer one topic per file, named in lowercase with hyphens.
- Treat the current code and configuration as authoritative where a doc disagrees (see `AGENTS.md`).
