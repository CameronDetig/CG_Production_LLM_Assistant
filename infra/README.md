# Terraform adoption and independent releases

This repository owns Lambda and its Function URL, Cognito, DynamoDB conversations, ECR, execution roles, logs, and the S3/CloudFront web frontend. Networking, RDS, and production data buckets belong to the metadata extractor repository. The assistant consumes its versioned SSM contract; no parent checkout or shared Terraform state access is needed.

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

The existing account-wide GitHub OIDC provider is referenced, not duplicated or owned by this stack. Bootstrap creates a dedicated encrypted/versioned bucket and separate build, plan, and apply roles. It also grants the plan/apply roles the bounded permissions in `bootstrap/frontend-policy.tf` needed to create and manage the frontend resources. Apply this bootstrap update before planning the frontend release. Only the apply role can write production state; neither CI role can access bootstrap state. The extractor additionally creates a scan role. Review before applying:

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

Later bootstrap changes (for example, CI role permissions) use the remote state, with an administrator signed in. If the AWS CLI is signed in with `aws login`, export its temporary credentials first: the Terraform AWS provider cannot read that session type and otherwise fails with "No valid credential sources found".

```sh
eval "$(aws configure export-credentials --format env)"
terraform -chdir=infra/bootstrap init -backend-config=backend.hcl
terraform -chdir=infra/bootstrap plan -out=bootstrap.tfplan
# After reviewing:
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
```

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
2. Relevant main-branch pushes run checks and release the image for the newest commit that changed `backend/` (tag `sha-<that commit>`), building it only if ECR does not have it yet. Infrastructure-only pushes therefore still carry a backend change whose earlier release never applied. Manual dispatches resolve the current deployed image unless given a rollback digest. Builds use Linux AMD64 with Lambda-compatible manifest flags. A 25 GB free-disk check fails with guidance to select a larger runner if needed.
3. The plan role saves the binary plan privately in S3 under `plans/<run-id>/<attempt>/`, with a checksum/commit manifest. Logs contain a resource/action summary, not sensitive plan values. Review the complete plan locally with `terraform show` after downloading it using authorized AWS credentials. Do not post plan JSON publicly.
4. Run **Approve production release** on main with the reviewed **plan run ID**. It verifies the successful source workflow, repository, event, branch, attempt, commit, checksum, and a 24-hour expiry. It checks out the plan commit and applies that exact saved plan. An expired plan or stale state requires a new plan and approval; apply never silently replans.
5. The workflow verifies Lambda/Batch control-plane status. Complete the runtime checks below before treating the release as accepted.

The approval workflow is always explicit, with an additional environment-review gate when configured. All release/approval runs share a per-repository concurrency group and native S3 state locking. Saved plan contents are sensitive even when variables are marked sensitive. S3 blocks public access and expires plan objects and noncurrent versions; production state versions have no expiry.

For rollback, dispatch the plan workflow with a retained `sha256:...` image digest, then review/approve the resulting plan. For an infra/configuration rollback, make a reviewed source revert and plan again. Each backend build receives both an immutable `sha-<commit>` tag and a sequential `vN` tag. The current ECR lifecycle policy retains the latest three versioned images, and expires `sha-`-only images after 30 days and untagged images after 7 days. Add any future retention changes separately, accounting for deployed and rollback digests.

The old direct deployment scripts are disabled to prevent competing ownership.

### Removing a resource

Releases reject any plan that deletes or replaces a resource. To retire one, replace its `resource` block with a `removed` block using `lifecycle { destroy = false }`. The plan then shows a `forget` action, which releases allow. After that release is applied, Terraform no longer manages the resource, and you delete it by hand with an administrator account. Do it in this order: if the resource is deleted first, the next plan tries to recreate it. Keep the `removed` blocks afterwards as history, like the import blocks.

The retired API Gateway HTTP API was removed this way on 2026-11-15 (`removed` blocks in `frontend.tf`). After its release was applied, the manual cleanup was:

```sh
api_id=$(aws apigatewayv2 get-apis --region us-east-1 --query "Items[?Name=='cg-assistant-frontend-api'].ApiId" --output text)
aws apigatewayv2 delete-api --api-id "$api_id" --region us-east-1   # also deletes its stage, routes, integration and authorizer
aws lambda remove-permission --function-name cg-production-chatbot --statement-id AllowApiGatewayInvoke --region us-east-1
```

## Web frontend release order

1. Apply the reviewed `infra/bootstrap` update so CI can inspect and create the new resource types.
2. Merge and approve the normal assistant Terraform release. This creates the private site/log buckets, CloudFront distribution, WAF, Cognito public client, runtime `config.json`, and frontend deployment role; it also enables Lambda response streaming and CloudFront-only invocation.
3. After the Terraform apply completes, dispatch **Approve production release** with the plan run ID blank and **deploy frontend** ticked (see `docs/ci-cd.md`). Deployment is manual, and it fails if the deployment role does not exist yet, which is why step 2 comes first. The workflow never overwrites Terraform-owned `config.json`.

The CloudFront hostname is the only initial public URL. Hashed assets receive immutable caching; HTML is deployed with revalidation and explicitly invalidated. The distribution is on the CloudFront flat-rate Free plan (below), which covers CloudFront and WAF. S3 storage/requests, Lambda streaming duration, and Cognito active-user usage can still add cost.

## CloudFront flat-rate Free plan

The distribution is billed on the CloudFront flat-rate **Free** plan ($0/month). The plan includes the WAF web ACL, its rules and its requests, which cost about $8/month on pay-as-you-go. The `*.cloudfront.net` URL is unchanged. The plan covers 1M requests and 100 GB per month with no overage charges; sustained traffic above that can be slowed, and the fix is to upgrade to Pro ($15/month).

Plan rules this configuration must keep to:
- A WAF web ACL must stay associated with the distribution. Keep `aws_wafv2_web_acl.frontend` and stay within **5 rules** (3 are used today). Header-based and regex-based matching, CAPTCHA, and Bot Control need a paid tier.
- Use **AWS-managed** response headers, cache and origin request policies only. Custom ones need the Business tier. The CSP lives in `frontend_web/csp.ts` as a meta tag instead.
- No CloudFront access logs or WAF request logs (Pro tier). The `frontend_logs` bucket still receives S3 server access logs for the site bucket.

AWS provider 6.23.0 and AWS CLI v2 have no pricing-plan API, so the subscription is a one-time console step. Do it after the Terraform release that removes the custom headers policy and the logging:

1. Apply the reviewed release. Its plan shows `forget` for `aws_cloudfront_response_headers_policy.security`, `aws_wafv2_web_acl_logging_configuration.frontend`, and `aws_cloudwatch_log_group.waf`. They leave state without being destroyed (see "Removing a resource" above).
2. Delete the retired resources by hand:
   ```powershell
   $acl = aws wafv2 list-web-acls --scope CLOUDFRONT --region us-east-1 --query "WebACLs[?Name=='cg-assistant-web'].ARN" --output text
   aws wafv2 delete-logging-configuration --resource-arn $acl --region us-east-1
   aws logs delete-log-group --log-group-name aws-waf-logs-cg-assistant-web --region us-east-1
   $id = aws cloudfront list-response-headers-policies --type custom --query "ResponseHeadersPolicyList.Items[?ResponseHeadersPolicy.ResponseHeadersPolicyConfig.Name=='cg-assistant-security-headers'].ResponseHeadersPolicy.Id" --output text
   $etag = aws cloudfront get-response-headers-policy --id $id --query ETag --output text
   aws cloudfront delete-response-headers-policy --id $id --if-match $etag
   ```
3. CloudFront console → the distribution → **Pricing plan** → **Manage plan** → choose **Free**. The console lists any remaining unsupported features.
4. Run `terraform plan` with the release inputs and confirm it shows no drift.

To leave the plan, cancel it in the console first (see [Manage your flat-rate pricing plans](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html)). Only after the distribution is back on pay-as-you-go can the web ACL be removed, or custom headers or logging re-added.

## Runtime acceptance and operational limits

- Assistant: authenticate through Cognito managed login; run a chat/search query; verify response chunks arrive before completion, read-only SQL enforcement, conversation persistence, signed thumbnail/source links, image search, and conversation deletion. Confirm the Lambda Function URL rejects direct requests and CloudFront `/api/health` succeeds. Verify failure responses do not expose credentials. The control-plane smoke check alone does not establish application health.
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
python -m unittest discover -s tests/infra -p 'test_*.py'
$env:PYTHONPATH = 'backend'; python -m unittest discover -s tests/backend -p 'test_*.py'
npm --prefix frontend_web ci
npm --prefix frontend_web test
npm --prefix frontend_web run lint
npm --prefix frontend_web run build
```

Sources: [Terraform imports](https://developer.hashicorp.com/terraform/language/import), [S3 state and locking](https://developer.hashicorp.com/terraform/language/backend/s3), [GitHub OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [GitHub environment restrictions](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
