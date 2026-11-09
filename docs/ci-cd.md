# CI/CD

Workflows live in `.github/workflows/`. AWS access uses GitHub OIDC with separate roles per purpose. There are no stored AWS secrets. Infrastructure is owned by `infra/` (see `infra/README.md`).

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `backend-checks.yml` | Every PR | `test` job: mocked regression tests (`testing.test_streaming`, `testing/test_cognito.py`, `testing/test_warmup.py`). `image` job: no-push Docker build with a GHA cache and a 25 GB free-disk check. |
| `infra-checks.yml` | Every PR | `validate` job: Terraform `fmt`, `init`, `validate` for `infra/` and `infra/bootstrap/`, plus the `infra/tools` unit tests. |
| `deploy-backend.yml` ("Plan assistant release") | Push to `main` touching `backend/**` or `infra/**`; manual dispatch | Saves a private Terraform plan to S3. **Never applies anything.** It builds and pushes the image to ECR (tags `sha-<commit>` and `v<N>`) only on a push that changes `backend/`; on infra-only pushes and manual dispatches it plans against the image that is already deployed. |
| `approve-release.yml` ("Approve production release") | Manual dispatch: optional plan run ID plus a "deploy frontend" checkbox (default on) | The single approval for everything. `apply` job (`production` environment, skipped if no plan ID): `release.py verify`, checks out the planned commit, then `apply` and `smoke`. Then the `frontend` job (if ticked): deploys the newest verified frontend build to S3, invalidates CloudFront and prunes old assets. |
| `deploy-frontend.yml` | Every PR; pushes to `main` touching `frontend_web/**` | Runs `verify` (tests, lint, build). On `main` it also uploads the tested `frontend-dist` artifact (kept 30 days). **Never deploys.** |

## Two-stage backend release

1. Merging backend or infra changes to `main` runs "Plan assistant release": build, push, plan. Nothing in production changes.
2. A human reviews the run and plan, then dispatches "Approve production release" with that plan run ID.
3. `infra/tools/release.py` (`verify` then `apply`):
   - verifies the plan's provenance: a successful run of the release-plan workflow on `main` in this repository, a manifest whose commit matches the run, a plan less than 24 hours old, and a matching file hash;
   - rejects the plan if `backend/`, `infra/` or the two release workflows changed on `main` since the planned commit, using the GitHub compare API. A truncated compare (300 or more files) is treated as superseded;
   - applies the exact saved plan.
4. `release.py smoke` checks the Lambda is active and running the image Terraform expects. It does not exercise the application.

Keep this rollout two-stage. Do not collapse it into a single automatic apply.

## Frontend release

1. Merging a change under `frontend_web/` runs `deploy-frontend.yml`, which verifies and saves the build. The live site does not change.
2. Dispatch **Approve production release**. Leave the plan run ID blank for a frontend-only release, or fill it in to release the backend too. Leave "deploy frontend" ticked to ship the frontend.
3. The `frontend` job runs after the backend apply and never after a failed one. It deploys the **newest** frontend build on `main`, with no rebuild, and refuses if that build is still running, failed or cancelled, or if its artifact has expired. It never falls back to an older build, so a superseded or broken change cannot overwrite the site.

A merged but unapproved change stays undeployed. Untick "deploy frontend" for a backend-only release.

## AWS roles

| Role | Used by | Trust (OIDC `sub`) |
|---|---|---|
| `github-cg-assistant-build` | `deploy-backend.yml` build job | `ref:refs/heads/main` |
| `github-cg-assistant-plan` | `deploy-backend.yml` plan job | `ref:refs/heads/main` |
| `github-cg-assistant-apply` | `approve-release.yml` | `environment:production` |
| `github-cg-assistant-frontend-deploy` | `approve-release.yml` `frontend` job | `ref:refs/heads/main` (defined in `infra/frontend.tf`) |

The build, plan and apply roles are defined in `infra/bootstrap/`.

## Constraints to keep in mind

- The `frontend` job in `approve-release.yml` deliberately has no `environment:` while the `apply` job does. **Do not add `environment:` to a job whose role trust pins `ref:refs/heads/main`.** A job environment changes the OIDC `sub` to `environment:<name>`, and the role would reject it. Change the role's trust policy in the same release if you need one.
- The frontend bucket is **versioned**, so `aws s3 sync --delete` only writes delete markers. It still removes the files from CloudFront's view.
- Hashed assets under `assets/` are published without `--delete`. A final step deletes `assets/` objects that are older than 14 days and absent from the current build, so open tabs and cached `index.html` files keep working across a release.
- `actions/upload-artifact` skips dotfiles. `frontend_web/public` currently holds only `config.json` and `favicon.svg`. Revisit this if files such as `.well-known/` are added.
- Every job has a `timeout-minutes`. Runners are pinned to `ubuntu-26.04`; bump the version deliberately when the image is retired.
- Backend applies and frontend deploys each use a non-cancelling concurrency group so they queue rather than overlap. PR verification for the frontend uses a separate cancellable group.

## Branch protection

A repository ruleset on `main` blocks deletion and force-pushes and requires the status checks `test`, `image`, `validate` and `verify`. It does **not** require pull requests, and repository admins can bypass it, so the owner can still push directly. A direct push by anyone without bypass is rejected, since the checks cannot have run yet.

The PR triggers of `backend-checks.yml`, `infra-checks.yml` and `deploy-frontend.yml` are deliberately unfiltered by path. A required check from a path-filtered workflow never reports on unrelated PRs and would block them. The `push` filters on the deploy workflows are kept, since they decide what gets deployed. Adding a new required check means its workflow must run on every PR.

## ECR

Repository `cg-chatbot` (defined in `infra/resources.tf`):
- Each image gets two tags: `sha-<commit>` and `v<N>`. Tags are **immutable**; pushing an existing tag fails. `deploy-backend.yml` reuses an existing `sha-` tag instead of rebuilding and only adds the new `v<N>` tag, and releases pin the image by digest.
- Basic scan-on-push is on (free). Findings are informational and do not block a release. Enhanced scanning (Amazon Inspector) is not enabled; it is billed per image.
- The lifecycle policy keeps the last 3 `v`-prefixed images.

## Known gaps

- No application-level smoke test after a deploy.
- The `production` GitHub environment has no required reviewers, so both approvals (backend and frontend) are deliberate manual dispatches rather than a recorded reviewer sign-off.
- Actions are pinned by tag rather than commit SHA, and there is no Dependabot for `github-actions`.

These are tracked as local specs and will be removed from this list as they are fixed.
