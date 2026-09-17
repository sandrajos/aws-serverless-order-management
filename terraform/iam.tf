# ---------------------------------------------------------------------------
# Shared assume-role policy for all Lambda execution roles
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# create_order role: write to DynamoDB, send to SQS, write its own logs
# ---------------------------------------------------------------------------
resource "aws_iam_role" "create_order" {
  name               = "${var.project_name}-create-order-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "create_order_policy" {
  statement {
    sid       = "DynamoDbReadWrite"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.orders.arn]
  }

  statement {
    sid       = "SendToOrdersQueue"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.orders_queue.arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}-create-order-${var.environment}*"]
  }
}

resource "aws_iam_role_policy" "create_order" {
  name   = "${var.project_name}-create-order-policy"
  role   = aws_iam_role.create_order.id
  policy = data.aws_iam_policy_document.create_order_policy.json
}

# ---------------------------------------------------------------------------
# process_order role: read/update DynamoDB, consume SQS, publish EventBridge
# ---------------------------------------------------------------------------
resource "aws_iam_role" "process_order" {
  name               = "${var.project_name}-process-order-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "process_order_policy" {
  statement {
    sid       = "DynamoDbReadUpdate"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.orders.arn]
  }

  statement {
    sid = "ConsumeOrdersQueue"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [aws_sqs_queue.orders_queue.arn]
  }

  statement {
    sid       = "PublishEvents"
    actions   = ["events:PutEvents"]
    resources = [data.aws_cloudwatch_event_bus.default.arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}-process-order-${var.environment}*"]
  }
}

resource "aws_iam_role_policy" "process_order" {
  name   = "${var.project_name}-process-order-policy"
  role   = aws_iam_role.process_order.id
  policy = data.aws_iam_policy_document.process_order_policy.json
}

data "aws_cloudwatch_event_bus" "default" {
  name = "default"
}

# ---------------------------------------------------------------------------
# notify role: just needs to write logs (SNS invokes it; no outbound calls
# beyond logging in this portfolio version)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "notify" {
  name               = "${var.project_name}-notify-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "notify_policy" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}-notify-${var.environment}*"]
  }
}

resource "aws_iam_role_policy" "notify" {
  name   = "${var.project_name}-notify-policy"
  role   = aws_iam_role.notify.id
  policy = data.aws_iam_policy_document.notify_policy.json
}
