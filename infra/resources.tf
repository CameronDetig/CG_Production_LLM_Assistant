# Adoption baseline generated from live AWS configuration. See README before applying.

resource "aws_iam_role_policy" "assistant_DynamoDBConversationsAccess" {
  name = "DynamoDBConversationsAccess"
  policy = jsonencode({
    Statement = [{
      Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan"]
      Effect   = "Allow"
      Resource = ["arn:aws:dynamodb:us-east-1:*:table/cg-chatbot-conversations", "arn:aws:dynamodb:us-east-1:*:table/cg-chatbot-conversations/index/*"]
    }]
    Version = "2012-10-17"
  })
  role = "cg-chatbot-lambda-role"
}

resource "aws_iam_role_policy_attachment" "assistant_AWSLambdaBasicExecutionRole" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = "cg-chatbot-lambda-role"
}

resource "aws_iam_role_policy" "assistant_S3ThumbnailAccess" {
  name = "S3ThumbnailAccess"
  policy = jsonencode({
    Statement = [{
      Action   = ["s3:GetObject"]
      Effect   = "Allow"
      Resource = "arn:aws:s3:::cg-production-data-thumbnails/*"
    }]
    Version = "2012-10-17"
  })
  role = "cg-chatbot-lambda-role"
}

resource "aws_lambda_permission" "function_url" {
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = "cg-production-chatbot"
  function_url_auth_type = "NONE"
  principal              = "*"
  region                 = "us-east-1"
  statement_id           = "FunctionURLAllowPublicAccess"
}

resource "aws_iam_role_policy_attachment" "assistant_AmazonBedrockFullAccess" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
  role       = "cg-chatbot-lambda-role"
}

resource "aws_cloudwatch_log_group" "application" {
  log_group_class   = "STANDARD"
  name              = "/aws/lambda/cg-production-chatbot"
  region            = "us-east-1"
  retention_in_days = 30
  skip_destroy      = false
  tags              = {}
}

resource "aws_ecr_lifecycle_policy" "application" {
  policy = jsonencode({
    rules = [{
      action = {
        type = "expire"
      }
      description  = "Keep only the last 3 tagged images"
      rulePriority = 1
      selection = {
        countNumber   = 3
        countType     = "imageCountMoreThan"
        tagPrefixList = ["v"]
        tagStatus     = "tagged"
      }
    }]
  })
  region     = "us-east-1"
  repository = "cg-chatbot"
}

resource "aws_iam_role_policy_attachment" "assistant_CloudWatchLogsFullAccess" {
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
  role       = "cg-chatbot-lambda-role"
}

resource "aws_iam_role_policy_attachment" "assistant_AmazonS3FullAccess" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  role       = "cg-chatbot-lambda-role"
}

resource "aws_iam_role_policy_attachment" "assistant_AWSLambdaVPCAccessExecutionRole_6a27889e_714f_404f_b7ac_34687fe19ca7" {
  policy_arn = "arn:aws:iam::001879457662:policy/service-role/AWSLambdaVPCAccessExecutionRole-6a27889e-714f-404f-b7ac-34687fe19ca7"
  role       = "cg-chatbot-lambda-role"
}

resource "aws_ecr_repository_policy" "application" {
  policy = jsonencode({
    Statement = [{
      Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:SetRepositoryPolicy", "ecr:DeleteRepositoryPolicy", "ecr:GetRepositoryPolicy"]
      Condition = {
        StringLike = {
          "aws:sourceArn" = "arn:aws:lambda:us-east-1:001879457662:function:*"
        }
      }
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Sid = "LambdaECRImageRetrievalPolicy"
    }]
    Version = "2008-10-17"
  })
  region     = "us-east-1"
  repository = "cg-chatbot"
}

resource "aws_dynamodb_table" "conversations" {
  lifecycle {
    prevent_destroy = true
  }
  billing_mode                = "PAY_PER_REQUEST"
  deletion_protection_enabled = false
  hash_key                    = "conversation_id"
  name                        = "cg-chatbot-conversations"
  range_key                   = "user_id"
  read_capacity               = 0
  region                      = "us-east-1"
  stream_enabled              = false
  table_class                 = "STANDARD"
  tags = {
    Project = "CG-Production-Assistant"
  }
  write_capacity = 0
  attribute {
    name = "conversation_id"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }
  global_secondary_index {
    hash_key           = "user_id"
    name               = "user_id-created_at-index"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "created_at"
    read_capacity      = 0
    write_capacity     = 0
  }
  point_in_time_recovery {
    enabled                 = false
    recovery_period_in_days = 35
  }
  ttl {
    enabled = false
  }
}

resource "aws_iam_policy" "assistant_AWSLambdaVPCAccessExecutionRole_6a27889e_714f_404f_b7ac_34687fe19ca7" {
  name = "AWSLambdaVPCAccessExecutionRole-6a27889e-714f-404f-b7ac-34687fe19ca7"
  path = "/service-role/"
  policy = jsonencode({
    Statement = [{
      Action   = ["ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:DescribeNetworkInterfaces"]
      Effect   = "Allow"
      Resource = "*"
    }]
    Version = "2012-10-17"
  })
  tags = {}
}

resource "aws_lambda_function_url" "assistant" {
  authorization_type = "NONE"
  function_name      = "cg-production-chatbot"
  invoke_mode        = "BUFFERED"
  region             = "us-east-1"
  cors {
    allow_credentials = false
    allow_headers     = ["*"]
    allow_methods     = ["*"]
    allow_origins     = ["*"]
    expose_headers    = []
    max_age           = 86400
  }
}

resource "aws_cognito_user_pool_domain" "users" {
  domain                = "us-east-1olfysymle"
  managed_login_version = 2
  region                = "us-east-1"
  user_pool_id          = "us-east-1_olfysYmLE"
}

resource "aws_cognito_user_pool_client" "assistant" {
  lifecycle {
    prevent_destroy = true
  }
  access_token_validity                         = 60
  allowed_oauth_flows                           = []
  allowed_oauth_flows_user_pool_client          = false
  allowed_oauth_scopes                          = []
  auth_session_validity                         = 3
  callback_urls                                 = []
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  explicit_auth_flows                           = ["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_AUTH", "ALLOW_USER_PASSWORD_AUTH", "ALLOW_USER_SRP_AUTH"]
  id_token_validity                             = 60
  logout_urls                                   = []
  name                                          = "cg-production-assistant-client"
  prevent_user_existence_errors                 = "ENABLED"
  read_attributes                               = []
  refresh_token_validity                        = 5
  region                                        = "us-east-1"
  supported_identity_providers                  = []
  user_pool_id                                  = "us-east-1_olfysYmLE"
  write_attributes                              = []
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_ecr_repository" "application" {
  lifecycle {
    prevent_destroy = true
  }
  image_tag_mutability = "MUTABLE"
  name                 = "cg-chatbot"
  region               = "us-east-1"
  tags                 = {}
  encryption_configuration {
    encryption_type = "AES256"
  }
  image_scanning_configuration {
    scan_on_push = false
  }
}

resource "aws_iam_role" "assistant" {
  assume_role_policy = jsonencode({
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
    Version = "2012-10-17"
  })
  description           = "Allows Lambda chatbot function access to production data and thumbnail buckets"
  force_detach_policies = false
  max_session_duration  = 3600
  name                  = "cg-chatbot-lambda-role"
  path                  = "/"
  tags                  = {}
}

resource "aws_lambda_function" "assistant" {
  lifecycle {
    prevent_destroy = true
  }
  architectures                  = ["x86_64"]
  function_name                  = "cg-production-chatbot"
  image_uri                      = coalesce(var.image_uri, "001879457662.dkr.ecr.us-east-1.amazonaws.com/cg-chatbot:v11")
  layers                         = []
  memory_size                    = 3072
  package_type                   = "Image"
  region                         = "us-east-1"
  reserved_concurrent_executions = -1
  role                           = "arn:aws:iam::001879457662:role/cg-chatbot-lambda-role"
  skip_destroy                   = false
  tags                           = {}
  timeout                        = 180
  environment {
    variables = local.environment
  }
  ephemeral_storage {
    size = 512
  }
  logging_config {
    log_format = "Text"
    log_group  = "/aws/lambda/cg-production-chatbot"
  }
  tracing_config {
    mode = "PassThrough"
  }
}

resource "aws_cognito_user_pool" "users" {
  lifecycle {
    prevent_destroy = true
  }
  auto_verified_attributes = []
  deletion_protection      = "ACTIVE"
  mfa_configuration        = "OFF"
  name                     = "cg-production-assistant-user-pool"
  region                   = "us-east-1"
  tags                     = {}
  user_pool_tier           = "ESSENTIALS"
  username_attributes      = ["email"]
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
    recovery_mechanism {
      name     = "verified_phone_number"
      priority = 2
    }
  }
  admin_create_user_config {
    allow_admin_create_user_only = false
  }
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }
  password_policy {
    minimum_length                   = 8
    password_history_size            = 0
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }
  sign_in_policy {
    allowed_first_auth_factors = ["PASSWORD"]
  }
  username_configuration {
    case_sensitive = false
  }
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }
}
