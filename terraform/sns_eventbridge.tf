resource "aws_sns_topic" "order_notifications" {
  name = "${var.project_name}-order-notifications-${var.environment}"
}

# Optional: subscribe an operator/demo email to notifications directly
# (in addition to the notify Lambda), useful for quickly demoing the
# end-to-end flow without checking CloudWatch Logs.
resource "aws_sns_topic_subscription" "email_demo" {
  count     = var.alarm_notification_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.order_notifications.arn
  protocol  = "email"
  endpoint  = var.alarm_notification_email
}

resource "aws_sns_topic_subscription" "notify_lambda" {
  topic_arn = aws_sns_topic.order_notifications.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.notify.arn
}

resource "aws_lambda_permission" "sns_invoke_notify" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notify.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.order_notifications.arn
}

# EventBridge rule: route OrderProcessed events (emitted by process_order)
# to the SNS topic, which fans out to the notify Lambda (and optionally a
# human's email for demo purposes).
resource "aws_cloudwatch_event_rule" "order_processed" {
  name           = "${var.project_name}-order-processed-${var.environment}"
  description    = "Routes OrderProcessed events to the notification topic"
  event_bus_name = data.aws_cloudwatch_event_bus.default.name

  event_pattern = jsonencode({
    source      = ["orders.platform"]
    detail-type = ["OrderProcessed"]
  })
}

resource "aws_cloudwatch_event_target" "order_processed_to_sns" {
  rule           = aws_cloudwatch_event_rule.order_processed.name
  event_bus_name = data.aws_cloudwatch_event_bus.default.name
  arn            = aws_sns_topic.order_notifications.arn
}

resource "aws_sns_topic_policy" "allow_eventbridge_publish" {
  arn = aws_sns_topic.order_notifications.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgePublish"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = aws_sns_topic.order_notifications.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.order_processed.arn
          }
        }
      }
    ]
  })
}
