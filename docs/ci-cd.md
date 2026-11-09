# CI/CD

Workflows live in `.github/workflows/`. AWS access uses GitHub OIDC with separate roles per purpose. There are no stored AWS secrets. Infrastructure is owned by `infra/` (see `infra/README.md`).

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `backend-checks.yml` | PRs touching `backend/**` | `test` job: mocked regression tests (`testing.test_streaming`, `testing/test_cognito.py`, `testing/test_warmup.py`). `image` job: no-push Docker build with a GHA cache and a 25 GB free-disk check. |
| `infra-checks.yml` | PRs touching `infra/**` or workflows | `validate` job: Terraform `fmt`, `init`, `validate` for `infra/` and `infra/bootstrap/`, plus the `infra/tools` unit tests. |
| `deploy-backend.yml` ("Plan assistant release") | Push to `main` touching `backend/**` or `infra/**`; manual dispatch | Builds the image to ECR (tags `sha-<commit>` and `v<N>`) and saves a private Terraform plan to S3. **Never applies anything.** |
| `approve-release.yml` ("Approve production release") | Manual dispatch with a plan run ID; `production` environment | `release.py verify`, checks out the planned commit, then `apply` and `smoke`. |
| `deploy-frontend.yml` | PRs touching `frontend_web/**` run `verify` only; pushes to `main` also deploy | Builds and tests in `verify`, uploads a `frontend-dist` artifact, then the `deploy` job (main only) syncs to S3, invalidates CloudFront and prunes old assets. There is currently no approval step. |

## Two-stage backend release

1. Merging backend or infra changes to `main` runs "Plan assistant release": build, push, plan. Nothing in production changes.
2. A human reviews the run and plan, then dispatches "Approve production release" with that plan run ID.
3. `infra/tools/release.py` (`verify` then `apply`):
   - verifies the plan's provenance: a successful run of the release-plan workflow on `main` in this repository, a manifest whose commit matches the run, a plan less than 24 hours old, and a matching file hash;
   - rejects the plan if `backend/`, `infra/` or the two release workflows changed on `main` since the planned commit, using the GitHub compare API. A truncated compare (300 or more files) is treated as superseded;
   - applies the exact saved plan.
4. `release.py smoke` checks the Lambda is active and running the image Terraform expects. It does not exercise the application.

Keep this rollout two-stage. Do not collapse it into a single automatic apply.

## AWS roles

| Role | Used by | Trust (OIDC `sub`) |
|---|---|---|
| `github-cg-assistant-build` | `deploy-backend.yml` build job | `ref:refs/heads/main` |
| `github-cg-assistant-plan` | `deploy-backend.yml` plan job | `ref:refs/heads/main` |
| `github-cg-assistant-apply` | `approve-release.yml` | `environment:production` |
| `github-cg-assistant-frontend-deploy` | `deploy-frontend.yml` deploy job | `ref:refs/heads/main` (defined in `infra/frontend.tf`) |

The build, plan and apply roles are defined in `infra/bootstrap/`.

## Constraints to keep in mind

- **Do not add `environment:` to a job whose role trust pins `ref:refs/heads/main`.** A job environment changes the OIDC `sub` to `environment:<name>`, and the role would reject it. Change the role's trust policy in the same release if you need one.
- The frontend bucket is **versioned**, so `aws s3 sync --delete` only writes delete markers. It still removes the files from CloudFront's view.
- Hashed assets under `assets/` are published without `--delete`. A final step deletes `assets/` objects that are older than 14 days and absent from the current build, so open tabs and cached `index.html` files keep working across a release.
- `actions/upload-artifact` skips dotfiles. `frontend_web/public` currently holds only `config.json` and `favicon.svg`. Revisit this if files such as `.well-known/` are added.
- Every job has a `timeout-minutes`. Runners are pinned to `ubuntu-26.04`; bump the version deliberately when the image is retired.
- Production deploys use concurrency groups so they queue rather than overlap. PR verification for the frontend uses a separate cancellable group.

## Known gaps

- No application-level smoke test after a deploy.
- The `production` GitHub environment has no required reviewers, so the "approval" is a deliberate manual dispatch.
- `main` has no branch protection or ruleset.
- ECR tags are mutable and scan-on-push is off.
- Actions are pinned by tag rather than commit SHA, and there is no Dependabot for `github-actions`.

These are tracked as local specs and will be removed from this list as they are fixed.
