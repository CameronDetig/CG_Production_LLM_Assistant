# Live AWS adoption inventory — 2026-09-05

Source: read-only AWS CLI calls using the operator's `AdminUser` profile, account `001879457662`, region `us-east-1`. Exact import identifiers are in `imports.tf.json`. No secret values are recorded here.

| Resource | Observed configuration | Owner |
|---|---|---|
| VPC `vpc-04bb7be45c9d6b7f7` | `172.30.0.0/16`, six /24 public subnets, one main route table and internet gateway; no VPC endpoints | Extractor |
| RDS `cg-metadata-db` | PostgreSQL 17.9, db.t4g.micro, encrypted gp3 20 GB, autoscaling max 1000 GB, Single-AZ, **private**, one-day backups | Extractor |
| Production S3 | `cg-production-data`, `cg-production-data-thumbnails`; existing encryption/public-access/lifecycle/policy settings retained | Extractor |
| Secret `cg-metadata-db/database-url` | Batch injects the `url` JSON key; value is not Terraform-managed | Extractor |
| Batch `cg-metadata-compute` | Fargate, max 32 vCPUs, six subnets, default VPC security group | Extractor |
| Queue `cg-metadata-queue` | Enabled, priority 1 | Extractor |
| Job `cg-metadata-job:36` | 8 vCPUs, 53248 MiB RAM, public IP enabled, `OVERRIDE_EXISTING=false`, 4 scanner workers, `shows/` prefix | Extractor |
| ECR | `cg-metadata-extractor`, `cg-chatbot`; current tag mutability/lifecycle retained | Respective component |
| Lambda `cg-production-chatbot` | x86_64 image, 3072 MB RAM, 180-second timeout, 512 MB temporary disk, **no VPC attachment** | Assistant |
| Lambda image | `cg-chatbot:v11`, resolved digest `sha256:5a651f179f5d4aef647a9635bd2fb622a8afca615175cb4ea0e22425708dc71b` | Assistant |
| Function URL | Existing public-auth (`NONE`) URL, `BUFFERED` invocation, existing CORS; authentication remains in application code | Assistant |
| Cognito | Pool `us-east-1_olfysYmLE`, client `7fjti9ulrj9rgoq0lgs9g8eobg`, existing domain; pool deletion protection active | Assistant |
| DynamoDB | `cg-chatbot-conversations`, PAY_PER_REQUEST; conversation_id/user_id keys, user_id-created_at-index retained | Assistant |
| Logs | `/aws/batch/job` and `/aws/lambda/cg-production-chatbot`, both 30-day retention | Respective component |
| GitHub OIDC | Existing account provider `token.actions.githubusercontent.com`; reused by bootstrap | Existing account resource |

The Lambda/private-RDS mismatch is a known runtime concern, not corrected by the adoption. Existing runtime roles include broad managed policies; they are preserved to avoid changing authorization during import. New CI roles have separate scoped build, plan, apply, and (extractor only) scan permissions.

Testing buckets, unused security groups, service-managed Batch ECS resources, unrelated applications/log groups, and the existing unzip Lambda are outside this production adoption. Assets, database records, Cognito users, and secret versions are not imported or recreated.

No AWS mutations were performed during inventory or local validation. Bootstrap and production adoption must be reviewed/applied separately.
