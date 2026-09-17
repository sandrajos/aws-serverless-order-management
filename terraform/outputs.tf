output "api_invoke_url" {
  description = "Base URL for the Order Management API"
  value       = aws_api_gateway_stage.orders_api.invoke_url
}

output "orders_table_name" {
  description = "DynamoDB table name for orders"
  value       = aws_dynamodb_table.orders.name
}

output "orders_queue_url" {
  description = "SQS queue URL for order processing"
  value       = aws_sqs_queue.orders_queue.url
}

output "orders_queue_arn" {
  description = "SQS queue ARN for order processing (used for DLQ redrive)"
  value       = aws_sqs_queue.orders_queue.arn
}

output "dlq_url" {
  description = "SQS Dead Letter Queue URL"
  value       = aws_sqs_queue.orders_dlq.url
}

output "dlq_arn" {
  description = "SQS Dead Letter Queue ARN (used for DLQ redrive)"
  value       = aws_sqs_queue.orders_dlq.arn
}

output "order_notifications_topic_arn" {
  description = "SNS topic ARN for order notifications"
  value       = aws_sns_topic.order_notifications.arn
}

output "ops_alerts_topic_arn" {
  description = "SNS topic ARN for operational CloudWatch alarms"
  value       = aws_sns_topic.ops_alerts.arn
}

output "dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.order_platform.dashboard_name}"
}
