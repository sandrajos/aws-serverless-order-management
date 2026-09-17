# ---------------------------------------------------------------------------
# Packaging: each Lambda gets its own zip containing its handler + the
# shared "common" module, so each function stays independently deployable.
# ---------------------------------------------------------------------------
locals {
  src_root = "${path.module}/../src"
  build_dir = "${path.module}/.build"
}

resource "null_resource" "package_create_order" {
  triggers = {
    handler_hash = filesha256("${local.src_root}/create_order/handler.py")
    common_hash  = filesha256("${local.src_root}/common/utils.py")
    db_hash      = filesha256("${local.src_root}/common/db.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ${local.build_dir}/create_order/common
      cp ${local.src_root}/create_order/handler.py ${local.build_dir}/create_order/
      cp ${local.src_root}/common/*.py ${local.build_dir}/create_order/common/
    EOT
  }
}

data "archive_file" "create_order" {
  type        = "zip"
  source_dir  = "${local.build_dir}/create_order"
  output_path = "${local.build_dir}/create_order.zip"
  depends_on  = [null_resource.package_create_order]
}

resource "null_resource" "package_process_order" {
  triggers = {
    handler_hash = filesha256("${local.src_root}/process_order/handler.py")
    common_hash  = filesha256("${local.src_root}/common/utils.py")
    db_hash      = filesha256("${local.src_root}/common/db.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ${local.build_dir}/process_order/common
      cp ${local.src_root}/process_order/handler.py ${local.build_dir}/process_order/
      cp ${local.src_root}/common/*.py ${local.build_dir}/process_order/common/
    EOT
  }
}

data "archive_file" "process_order" {
  type        = "zip"
  source_dir  = "${local.build_dir}/process_order"
  output_path = "${local.build_dir}/process_order.zip"
  depends_on  = [null_resource.package_process_order]
}

resource "null_resource" "package_notify" {
  triggers = {
    handler_hash = filesha256("${local.src_root}/notify/handler.py")
    common_hash  = filesha256("${local.src_root}/common/utils.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ${local.build_dir}/notify/common
      cp ${local.src_root}/notify/handler.py ${local.build_dir}/notify/
      cp ${local.src_root}/common/*.py ${local.build_dir}/notify/common/
    EOT
  }
}

data "archive_file" "notify" {
  type        = "zip"
  source_dir  = "${local.build_dir}/notify"
  output_path = "${local.build_dir}/notify.zip"
  depends_on  = [null_resource.package_notify]
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

  filename         = data.archive_file.create_order.output_path
  source_code_hash = data.archive_file.create_order.output_base64sha256

  environment {
    variables = {
      ORDERS_TABLE_NAME = aws_dynamodb_table.orders.name
      ORDERS_QUEUE_URL  = aws_sqs_queue.orders_queue.url
      LOG_LEVEL         = "INFO"
    }
  }
}

resource "aws_lambda_function" "process_order" {
  function_name                 = "${var.project_name}-process-order-${var.environment}"
  role                           = aws_iam_role.process_order.arn
  handler                        = "handler.handler"
  runtime                        = var.lambda_runtime
  timeout                        = 30
  memory_size                    = 256
  reserved_concurrent_executions = var.process_order_reserved_concurrency

  filename         = data.archive_file.process_order.output_path
  source_code_hash = data.archive_file.process_order.output_base64sha256

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

  filename         = data.archive_file.notify.output_path
  source_code_hash = data.archive_file.notify.output_base64sha256

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups (explicit, so retention is enforced from day one)
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
