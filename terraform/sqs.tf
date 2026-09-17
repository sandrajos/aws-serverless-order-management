resource "aws_sqs_queue" "orders_dlq" {
  name                      = "${var.project_name}-orders-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "orders_queue" {
  name                       = "${var.project_name}-orders-queue-${var.environment}"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600 # 4 days
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount      = var.sqs_max_receive_count
  })
}

# Allow the DLQ to be a redrive target for orders_queue
resource "aws_sqs_queue_redrive_allow_policy" "orders_dlq_allow" {
  queue_url = aws_sqs_queue.orders_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.orders_queue.arn]
  })
}

resource "aws_lambda_event_source_mapping" "process_order_sqs" {
  event_source_arn                  = aws_sqs_queue.orders_queue.arn
  function_name                     = aws_lambda_function.process_order.arn
  batch_size                        = 10
  maximum_batching_window_in_seconds = 5
  function_response_types           = ["ReportBatchItemFailures"]
}
