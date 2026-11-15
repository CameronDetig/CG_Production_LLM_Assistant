locals {
  frontend_bucket_name = "cg-assistant-web-001879457662-us-east-1"
  frontend_log_bucket  = "cg-assistant-web-logs-001879457662-us-east-1"
  # The API origin is the Lambda Function URL host. It streams responses (RESPONSE_STREAM);
  # API Gateway HTTP APIs cannot, which would make the chat arrive in one piece.
  api_origin     = replace(trimsuffix(aws_lambda_function_url.assistant.function_url, "/"), "https://", "")
  cloudfront_url = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

# The CloudFront flat-rate Free plan does not allow custom response headers policies, so the
# distribution uses the AWS-managed one (HSTS, nosniff, X-Frame-Options, Referrer-Policy).
# The Content-Security-Policy is a <meta> tag injected into index.html at build time
# (see frontend_web/csp.ts).
data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_s3_bucket" "frontend" {
  bucket = local.frontend_bucket_name
  tags = {
    Project = "CG-Production-Assistant"
  }
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled       = true
    blocked_encryption_types = ["SSE-C"]
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    id     = "expire-old-site-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket" "frontend_logs" {
  bucket = local.frontend_log_bucket
  tags = {
    Project = "CG-Production-Assistant"
  }
}

resource "aws_s3_bucket_ownership_controls" "frontend_logs" {
  bucket = aws_s3_bucket.frontend_logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend_logs" {
  bucket                  = aws_s3_bucket.frontend_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend_logs" {
  bucket = aws_s3_bucket.frontend_logs.id
  rule {
    bucket_key_enabled       = false
    blocked_encryption_types = ["SSE-C"]
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_acl" "frontend_logs" {
  depends_on = [aws_s3_bucket_ownership_controls.frontend_logs]
  bucket     = aws_s3_bucket.frontend_logs.id
  acl        = "log-delivery-write"
}

resource "aws_s3_bucket_lifecycle_configuration" "frontend_logs" {
  bucket = aws_s3_bucket.frontend_logs.id
  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = 90
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_logging" "frontend" {
  bucket        = aws_s3_bucket.frontend.id
  target_bucket = aws_s3_bucket.frontend_logs.id
  target_prefix = "s3-access/"
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "cg-assistant-web-s3"
  description                       = "Private S3 origin for the assistant SPA"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_origin_access_control" "api" {
  name                              = "cg-assistant-api-lambda"
  description                       = "Private Lambda Function URL origin"
  origin_access_control_origin_type = "lambda"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# The retired API Gateway HTTP API. CloudFront routes /api/* to the Lambda Function URL
# (see local.api_origin) and these resources are no longer used. Release tooling rejects
# deletions, so Terraform only forgets them here (destroy = false); the API and its Lambda
# permission are then deleted by hand, as described in infra/README.md.
removed {
  from = aws_apigatewayv2_api.frontend
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_stage.frontend
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_integration.frontend
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_authorizer.frontend
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_route.health
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_route.auth
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_route.signup
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_apigatewayv2_route.authenticated
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_lambda_permission.api_gateway_invoke
  lifecycle {
    destroy = false
  }
}

# Moving to the CloudFront flat-rate Free plan retired these resources. Release tooling rejects
# deletions, so they leave state without being destroyed. Delete them by hand afterwards
# (see "CloudFront flat-rate Free plan" in infra/README.md).
removed {
  from = aws_cloudfront_response_headers_policy.security
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_wafv2_web_acl_logging_configuration.frontend
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_cloudwatch_log_group.waf
  lifecycle {
    destroy = false
  }
}

# The CloudFront flat-rate Free plan includes this web ACL at no charge and requires one to
# stay associated with the distribution. Keep it, and stay within the plan's 5-rule limit.
# WAF request logging is a Pro-tier feature, so none is configured.
resource "aws_wafv2_web_acl" "frontend" {
  name  = "cg-assistant-web"
  scope = "CLOUDFRONT"
  default_action {
    allow {}
  }
  rule {
    name     = "AWSManagedCommonRules"
    priority = 0
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "cg-assistant-common-rules"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "CompatibilityAuthRateLimit"
    priority = 1
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300
        limit                 = 50
        scope_down_statement {
          or_statement {
            statement {
              byte_match_statement {
                positional_constraint = "EXACTLY"
                search_string         = "/api/auth"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
            statement {
              byte_match_statement {
                positional_constraint = "EXACTLY"
                search_string         = "/api/signup"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "cg-assistant-auth-rate-limit"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "ApiRateLimit"
    priority = 2
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300
        limit                 = 300
        scope_down_statement {
          byte_match_statement {
            positional_constraint = "STARTS_WITH"
            search_string         = "/api/"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "cg-assistant-api-rate-limit"
      sampled_requests_enabled   = true
    }
  }
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "cg-assistant-web-acl"
    sampled_requests_enabled   = true
  }
  tags = {
    Project = "CG-Production-Assistant"
  }
}

# Billed on the CloudFront flat-rate Free plan (subscribed outside Terraform; see
# infra/README.md). Features the plan does not allow (custom response headers policies,
# access logs) must not be added here, or the subscription will fail.
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  comment             = "CG Production Assistant web and API"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  web_acl_id          = aws_wafv2_web_acl.frontend.arn

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  origin {
    domain_name              = local.api_origin
    origin_id                = "assistant-api"
    origin_access_control_id = aws_cloudfront_origin_access_control.api.id
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id           = "frontend-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
    compress                   = true
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  ordered_cache_behavior {
    path_pattern               = "/api/*"
    target_origin_id           = "assistant-api"
    viewer_protocol_policy     = "https-only"
    allowed_methods            = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
    compress                   = false
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
    # With the default *.cloudfront.net certificate, CloudFront always enforces and reports
    # TLSv1 and ignores any other value, which showed up as a no-op diff in every plan.
    # Raising the minimum needs a custom domain with an ACM certificate.
    minimum_protocol_version = "TLSv1"
  }
  tags = {
    Project = "CG-Production-Assistant"
  }
}

resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "cg-assistant-spa-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Resolve extensionless SPA routes to index.html"
  publish = true
  code    = <<-EOT
    function handler(event) {
      var request = event.request;
      if (request.uri.indexOf('.') === -1) {
        request.uri = '/index.html';
      }
      return request;
    }
  EOT
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontRead"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
        Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn } }
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.frontend.arn, "${aws_s3_bucket.frontend.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }
    ]
  })
}

resource "aws_cognito_user_pool_client" "frontend" {
  name                                 = "cg-production-assistant-web"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email"]
  callback_urls                        = ["${local.cloudfront_url}/auth/callback"]
  logout_urls                          = [local.cloudfront_url]
  supported_identity_providers         = ["COGNITO"]
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"
  access_token_validity                = 60
  id_token_validity                    = 60
  refresh_token_validity               = 5
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  refresh_token_rotation {
    feature                    = "ENABLED"
    retry_grace_period_seconds = 30
  }
}

resource "aws_cognito_managed_login_branding" "frontend" {
  client_id                   = aws_cognito_user_pool_client.frontend.id
  user_pool_id                = aws_cognito_user_pool.users.id
  use_cognito_provided_values = true
}

resource "aws_s3_object" "frontend_config" {
  bucket        = aws_s3_bucket.frontend.id
  key           = "config.json"
  content_type  = "application/json"
  cache_control = "no-store"
  content = jsonencode({
    cognitoDomain   = "${aws_cognito_user_pool_domain.users.domain}.auth.us-east-1.amazoncognito.com"
    cognitoClientId = aws_cognito_user_pool_client.frontend.id
    oauthScopes     = ["openid", "email"]
  })
}

resource "aws_lambda_permission" "cloudfront_function_url" {
  statement_id           = "AllowCloudFrontFunctionURL"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.assistant.function_name
  principal              = "cloudfront.amazonaws.com"
  source_arn             = aws_cloudfront_distribution.frontend.arn
  function_url_auth_type = "AWS_IAM"
}

resource "aws_lambda_permission" "cloudfront_invoke" {
  statement_id  = "AllowCloudFrontInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.assistant.function_name
  principal     = "cloudfront.amazonaws.com"
  source_arn    = aws_cloudfront_distribution.frontend.arn
}

resource "aws_cloudwatch_metric_alarm" "frontend_5xx" {
  alarm_name          = "cg-assistant-cloudfront-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5xxErrorRate"
  namespace           = "AWS/CloudFront"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  dimensions = {
    DistributionId = aws_cloudfront_distribution.frontend.id
    Region         = "Global"
  }
}

resource "aws_cloudwatch_metric_alarm" "waf_blocks" {
  alarm_name          = "cg-assistant-waf-block-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  treat_missing_data  = "notBreaching"
  dimensions = {
    WebACL = "cg-assistant-web-acl"
    Region = "CloudFront"
    Rule   = "ALL"
  }
}

resource "aws_iam_role" "frontend_deploy" {
  name = "github-cg-assistant-frontend-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:CameronDetig/CG_Production_LLM_Assistant:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "frontend_deploy" {
  name = "DeployFrontend"
  role = aws_iam_role.frontend_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.frontend.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.frontend.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "cloudfront:CreateInvalidation"
        Resource = aws_cloudfront_distribution.frontend.arn
      },
      {
        Effect   = "Allow"
        Action   = "cloudfront:ListDistributions"
        Resource = "*"
      }
    ]
  })
}

output "frontend_url" {
  value = local.cloudfront_url
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.id
}

output "frontend_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}
