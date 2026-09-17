terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment and configure for a real deployment.
  # backend "s3" {
  #   bucket         = "my-terraform-state-bucket"
  #   key            = "order-platform/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "order-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}