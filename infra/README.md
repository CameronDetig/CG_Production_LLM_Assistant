# Terraform adoption and independent releases

This repository owns Lambda and its Function URL, Cognito, DynamoDB conversations, ECR, execution roles, and logs. Networking, RDS, and production buckets belong to the metadata extractor repository. The assistant consumes its versioned SSM contract; no parent checkout or shared Terraform state access is needed.

## Status and boundaries

The configuration was derived from live AWS account `001879457662`, region `us-east-1`, on 2026-09-05. See [INVENTORY.md](INVENTORY.md). The adoption check reviewed 20 imports without effective remote-value changes or replacements. Terraform has **not** been applied, CI roles/buckets have **not** been created, and GitHub releases have **not** been run. All changes are intentionally uncommitted for owner review.

This is an adoption configuration for the existing account, not a fresh-account installer. Persistent resources have `prevent_destroy`; release tooling also rejects every deletion/replacement. Existing sizing, networking, authentication, retention, broad runtime IAM policies, and secret delivery are preserved. Tightening those settings is a separate reviewed change. Database migrations, pgvector/schema setup, users, downloaded assets, and model data are not Terraform resources.

## Local inspection and one-time bootstrap

Install Terraform **1.14.7**, AWS CLI v2, and Python 3.11+. The AWS provider is pinned to **6.23.0**, with signed hashes for Windows and Linux in the checked-in lock files. Commands below run from this repository root in PowerShell. Never commit state, plans, `.private`, or runtime variable files.

```powershell
$env:AWS_PROFILE = 'AdminUser'
aws sts get-caller-identity
python infra/tools/inventory.py --component assistant --profile AdminUser
python infra/tools/check_adoption.py
```

`inventory.py` only reads AWS; it updates reviewable import IDs and stores raw, potentially secret-bearing material under ignored `.private/`. `check_adoption.py` copies source into a private local backend, runs plan, and rejects effective resource changes. It does not import into remote state or apply anything. Lambda can show one sensitivity-only environment update on first import: before/after values are identical. The checker verifies this rather than hiding environment drift with `ignore_changes`.

The existing account-wide GitHub OIDC provider is referenced, not duplicated or owned by this stack. Bootstrap creates a dedicated encrypted/versioned bucket and separate build, plan, and apply roles. Only the apply role can write production state; neither CI role can access bootstrap state. The extractor additionally creates a scan role. Review before applying:

```powershell
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap plan "-out=bootstrap.tfplan"
terraform -chdir=infra/bootstrap show bootstrap.tfplan
# After reviewing:
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
Copy-Item infra/bootstrap/backend.tf.example infra/bootstrap/backend.tf
terraform -chdir=infra/bootstrap init -migrate-state "-backend-config=backend.hcl"
```

Retain the bootstrap state backup until remote migration is verified. Include `infra/bootstrap/backend.tf` in a later commit after migration so subsequent checkouts initialize the remote backend. Do not rerun a local-bootstrap apply against an already bootstrapped account.

Configure GitHub environments `production` (and `production-scan` in the extractor) to allow **main only**. Add required reviewers if supported by your GitHub plan. Without reviewer support, the separate manually dispatched approval workflow is the approval gate. Only trusted maintainers should have write/workflow-dispatch access. Protect main and review workflow/IAM changes. OIDC role trust uses exact repository/main subjects for build/plan and the named environment for apply/scan. No AWS access keys belong in GitHub secrets.

## Import baseline before enabling releases

Create a fresh plan against the remote backend; do not apply a private local-backend plan to remote state. Pause manual console/script deployment while adopting.

```powershell
terraform -chdir=infra init "-backend-config=backend.hcl"
terraform -chdir=infra plan "-var-file=.private/runtime.auto.tfvars.json" "-out=.private/adoption.tfplan"
terraform -chdir=infra show .private/adoption.tfplan
# After reviewing the import-only baseline:
terraform -chdir=infra apply .private/adoption.tfplan
terraform -chdir=infra plan "-var-file=.private/runtime.auto.tfvars.json"
```

Import blocks are intentionally retained as adoption history. They do not reimport resources already in state. `image_uri = null` and the shared-contract flag defaulting to false exist for this first baseline only. **After the first ordinary release, do not plan without the release inputs:** doing so would restore the original image tag or remove the shared contract. Use the workflow or `release.py`, which resolves the current image and sets the contract flag.

Adopt and release the extractor first. Its first reviewed normal release publishes `/cg-production/prod/shared/v1` and pins the Batch image digest. Then adopt/release the assistant. The contract contains only identifiers: VPC/subnets/security groups, database host/port, bucket names, and secret ARN. It contains no passwords. The assistant reads it through SSM and merges database host/port and thumbnail bucket into its existing environment.

## Release, review, and rollback

1. Pull requests run Terraform validation and isolated release-guard tests without AWS credentials.
2. Relevant main-branch pushes run checks and build changed application code as `sha-<commit>`. Infrastructure-only changes resolve the current deployed image. Builds use Linux AMD64 with Lambda-compatible manifest flags. A 25 GB free-disk check fails with guidance to select a larger runner if needed.
3. The plan role saves the binary plan privately in S3 under `plans/<run-id>/<attempt>/`, with a checksum/commit manifest. Logs contain a resource/action summary, not sensitive plan values. Review the complete plan locally with `terraform show` after downloading it using authorized AWS credentials. Do not post plan JSON publicly.
4. Run **Approve production release** on main with the reviewed **plan run ID**. It verifies the successful source workflow, repository, event, branch, attempt, commit, checksum, and a 24-hour expiry. It checks out the plan commit and applies that exact saved plan. An expired plan or stale state requires a new plan and approval; apply never silently replans.
5. The workflow verifies Lambda/Batch control-plane status. Complete the runtime checks below before treating the release as accepted.

The approval workflow is always explicit, with an additional environment-review gate when configured. All release/approval runs share a per-repository concurrency group and native S3 state locking. Saved plan contents are sensitive even when variables are marked sensitive. S3 blocks public access and expires plan objects and noncurrent versions; production state versions have no expiry.

For rollback, dispatch the plan workflow with the retained `sha256:...` image digest, then review/approve the resulting plan. For an infra/configuration rollback, make a reviewed source revert and plan again. Current ECR lifecycle rules are preserved: new `sha-` tags are retained, so rollback images are not automatically removed. Add any future SHA-image cleanup policy separately, accounting for deployed digests.

The old direct deployment scripts are disabled to prevent competing ownership. Gradio's Hugging Face synchronization remains independent and unchanged.

## Runtime acceptance and operational limits

- Assistant: authenticate with an existing test user; run a chat/search query; verify read-only SQL enforcement, conversation persistence, signed thumbnail/source links, and the existing buffered response behavior. Verify failure responses do not expose credentials. The control-plane smoke check alone does not establish application health.
- Extractor: use small fixtures and an **isolated test database** for a container integration check before a large scan. Check metadata and thumbnail output. The production scan workflow is not this isolated integration test: it uses the production job's database secret.
- A normal extractor deployment never submits a scan. **Submit metadata scan** requires an explicit non-empty S3 prefix and exact job revision, uses the `production-scan` environment, and sets `OVERRIDE_EXISTING=false`. Concurrent/duplicate scan requests remain an operator responsibility; GitHub serialization covers submission, not job execution.
- Live Lambda has no VPC attachment while RDS is private. This is preserved during adoption and may prevent database access. Resolve connectivity in a separate reviewed change before claiming end-to-end success; do not make RDS public as part of import.
- Container builds and authenticated integration tests were not run locally because Docker is not running and a test-user/test-database setup was not supplied. GitHub runner sizing and OIDC permissions still require a first live release validation.

## Validation commands

```powershell
terraform -chdir=infra fmt -check
terraform -chdir=infra init -backend=false -lockfile=readonly
terraform -chdir=infra validate
terraform -chdir=infra/bootstrap init -backend=false -lockfile=readonly
terraform -chdir=infra/bootstrap validate
python -m unittest discover -s infra/tools -p 'test_*.py'
```

Sources: [Terraform imports](https://developer.hashicorp.com/terraform/language/import), [S3 state and locking](https://developer.hashicorp.com/terraform/language/backend/s3), [GitHub OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [GitHub environment restrictions](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
