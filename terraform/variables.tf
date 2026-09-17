variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Short name used as a prefix for resource names"
  type        = string
  default     = "order-platform"
}

variable "lambda_runtime" {
  description = "Python runtime version for all Lambda functions"
  type        = string
  default     = "python3.12"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 14
}

variable "sqs_max_receive_count" {
  description = "Number of times a message is retried before moving to the DLQ"
  type        = number
  default     = 3
}

variable "alarm_notification_email" {
  description = "Email address to subscribe to operational CloudWatch alarms (optional)"
  type        = string
  default     = ""
}

variable "process_order_reserved_concurrency" {
  description = "Reserved concurrency for the process_order Lambda, to protect downstream systems"
  type        = number
  default     = 10
}
