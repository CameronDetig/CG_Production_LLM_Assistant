locals {
  frontend_bucket_arns = [
    "arn:aws:s3:::cg-assistant-web-001879457662-us-east-1",
    "arn:aws:s3:::cg-assistant-web-001879457662-us-east-1/*",
    "arn:aws:s3:::cg-assistant-web-logs-001879457662-us-east-1",
    "arn:aws:s3:::cg-assistant-web-logs-001879457662-us-east-1/*",
  ]
}

resource "aws_iam_policy" "plan_frontend" {
  name = "github-cg-assistant-plan-frontend"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cloudfront:Get*", "cloudfront:List*", "cloudfront:DescribeFunction",
        "wafv2:Get*", "wafv2:List*",
        "s3:GetBucket*", "s3:GetEncryptionConfiguration", "s3:GetLifecycleConfiguration", "s3:GetObject", "s3:ListBucket",
        "logs:DescribeLogGroups", "logs:ListTagsForResource",
        "cloudwatch:DescribeAlarms", "cloudwatch:ListTagsForResource",
        "cognito-idp:DescribeUserPoolClient", "cognito-idp:DescribeManagedLoginBranding",
        "iam:GetRole", "iam:GetRolePolicy", "iam:GetOpenIDConnectProvider", "iam:ListOpenIDConnectProviders", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
      ]
      Resource = "*"
      }, {
      Effect = "Allow"
      Action = ["s3:GetAccelerateConfiguration", "s3:GetReplicationConfiguration"]
      Resource = [
        "arn:aws:s3:::cg-assistant-web-001879457662-us-east-1",
        "arn:aws:s3:::cg-assistant-web-logs-001879457662-us-east-1",
      ]
      }, {
      Effect   = "Allow"
      Action   = "s3:GetObjectTagging"
      Resource = "arn:aws:s3:::cg-assistant-web-001879457662-us-east-1/config.json"
      }, {
      Effect   = "Allow"
      Action   = "cognito-idp:ListUserPoolClients"
      Resource = "arn:aws:cognito-idp:us-east-1:001879457662:userpool/us-east-1_olfysYmLE"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "plan_frontend" {
  role       = aws_iam_role.plan.name
  policy_arn = aws_iam_policy.plan_frontend.arn
}

resource "aws_iam_policy" "apply_frontend" {
  name = "github-cg-assistant-apply-frontend"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:CreateBucket", "s3:DeleteBucket", "s3:Get*", "s3:ListBucket", "s3:Put*", "s3:DeleteObject",
        ]
        Resource = local.frontend_bucket_arns
      },
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateDistribution", "cloudfront:UpdateDistribution", "cloudfront:DeleteDistribution", "cloudfront:Get*", "cloudfront:List*", "cloudfront:TagResource", "cloudfront:UntagResource",
          "cloudfront:CreateOriginAccessControl", "cloudfront:UpdateOriginAccessControl", "cloudfront:DeleteOriginAccessControl",
          "cloudfront:CreateResponseHeadersPolicy", "cloudfront:UpdateResponseHeadersPolicy", "cloudfront:DeleteResponseHeadersPolicy",
          "cloudfront:CreateFunction", "cloudfront:UpdateFunction", "cloudfront:DeleteFunction", "cloudfront:DescribeFunction", "cloudfront:PublishFunction",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["wafv2:CreateWebACL", "wafv2:UpdateWebACL", "wafv2:DeleteWebACL", "wafv2:GetWebACL", "wafv2:ListTagsForResource", "wafv2:TagResource", "wafv2:UntagResource", "wafv2:PutLoggingConfiguration", "wafv2:DeleteLoggingConfiguration", "wafv2:GetLoggingConfiguration"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy", "logs:TagResource", "logs:UntagResource", "logs:PutResourcePolicy", "logs:DeleteResourcePolicy", "logs:CreateLogDelivery", "logs:DeleteLogDelivery", "logs:GetLogDelivery", "logs:ListLogDeliveries", "logs:UpdateLogDelivery"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms", "cloudwatch:DescribeAlarms", "cloudwatch:ListTagsForResource", "cloudwatch:TagResource", "cloudwatch:UntagResource"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:CreateUserPoolClient", "cognito-idp:UpdateUserPoolClient", "cognito-idp:DeleteUserPoolClient", "cognito-idp:DescribeUserPoolClient", "cognito-idp:ListUserPoolClients", "cognito-idp:CreateManagedLoginBranding", "cognito-idp:UpdateManagedLoginBranding", "cognito-idp:DeleteManagedLoginBranding", "cognito-idp:DescribeManagedLoginBranding"]
        Resource = "arn:aws:cognito-idp:us-east-1:001879457662:userpool/us-east-1_olfysYmLE"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy", "iam:TagRole", "iam:UntagRole"]
        Resource = "arn:aws:iam::001879457662:role/github-cg-assistant-frontend-deploy"
      },
      {
        Effect   = "Allow"
        Action   = "iam:CreateServiceLinkedRole"
        Resource = "arn:aws:iam::*:role/aws-service-role/wafv2.amazonaws.com/AWSServiceRoleForWAFV2Logging"
        Condition = {
          StringEquals = {
            "iam:AWSServiceName" = "wafv2.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "apply_frontend" {
  role       = aws_iam_role.apply.name
  policy_arn = aws_iam_policy.apply_frontend.arn
}
