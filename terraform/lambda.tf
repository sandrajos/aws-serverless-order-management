# ---------------------------------------------------------------------------
# Lambda deployment packages
#
# Run the cross-platform packaging script before terraform plan/apply:
#
#   python scripts/package_lambdas.py
#
# The generated ZIP files are stored under terraform/.build/.
# ---------------------------------------------------------------------------

locals {
  build_dir = "${path.module}/.build"
}

# ---------------------------------------------------------------------------
# Lambda functions
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "create_order" {
  function_name = "${var.project_name}-create-order-${var.environment}"
  role          = aws_iam_role.create_order.arn
  handler       = "handler.handler"
  runtime       = var.lambda_runtime
  timeout       = 10
  memory_size   = 256

  filename         = "${local.build_dir}/create_order.zip"
  source_code_hash = filebase64sha256("${local.build_dir}/create_order.zip")

  environment {
    variables = {
      ORDERS_TABLE_NAME = aws_dynamodb_table.orders.name
      ORDERS_QUEUE_URL  = aws_sqs_queue.orders_queue.url
      LOG_LEVEL         = "INFO"
    }
  }
}

resource "aws_lambda_function" "process_order" {
  function_name                  = "${var.project_name}-process-order-${var.environment}"
  role                           = aws_iam_role.process_order.arn
  handler                        = "handler.handler"
  runtime                        = var.lambda_runtime
  timeout                        = 30
  memory_size                    = 256
  reserved_concurrent_executions = var.process_order_reserved_concurrency

  filename         = "${local.build_dir}/process_order.zip"
  source_code_hash = filebase64sha256("${local.build_dir}/process_order.zip")

  environment {
    variables = {
      ORDERS_TABLE_NAME = aws_dynamodb_table.orders.name
      EVENT_BUS_NAME    = data.aws_cloudwatch_event_bus.default.name
      LOG_LEVEL         = "INFO"
    }
  }
}

resource "aws_lambda_function" "notify" {
  function_name = "${var.project_name}-notify-${var.environment}"
  role          = aws_iam_role.notify.arn
  handler       = "handler.handler"
  runtime       = var.lambda_runtime
  timeout       = 10
  memory_size   = 128

  filename         = "${local.build_dir}/notify.zip"
  source_code_hash = filebase64sha256("${local.build_dir}/notify.zip")

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
#
# Explicit log groups allow us to control retention from day one.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "create_order" {
  name              = "/aws/lambda/${aws_lambda_function.create_order.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "process_order" {
  name              = "/aws/lambda/${aws_lambda_function.process_order.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "notify" {
  name              = "/aws/lambda/${aws_lambda_function.notify.function_name}"
  retention_in_days = var.log_retention_days
}