variable "use_shared_contract" {
  description = "Enable after the extractor has published the shared SSM contract."
  type        = bool
  default     = false
}

data "aws_ssm_parameter" "shared" {
  count = var.use_shared_contract ? 1 : 0
  name  = "/cg-production/prod/shared/v1"
}

locals {
  shared = var.use_shared_contract ? jsondecode(nonsensitive(data.aws_ssm_parameter.shared[0].value)) : null
  environment = merge(var.lambda_environment, var.use_shared_contract ? {
    DB_HOST          = local.shared.database_host
    DB_PORT          = tostring(local.shared.database_port)
    THUMBNAIL_BUCKET = local.shared.thumbnail_bucket
  } : {})
}

output "api_endpoint" {
  value = aws_lambda_function_url.assistant.function_url
}
output "image_uri" {
  value = aws_lambda_function.assistant.image_uri
}
