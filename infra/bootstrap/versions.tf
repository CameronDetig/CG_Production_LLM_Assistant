terraform {
  required_version = "= 1.14.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.23.0"
    }
  }
}

provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = ["001879457662"]
}
