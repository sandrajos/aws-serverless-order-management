resource "aws_api_gateway_rest_api" "orders_api" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "Order Management API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# /orders
resource "aws_api_gateway_resource" "orders" {
  rest_api_id = aws_api_gateway_rest_api.orders_api.id
  parent_id   = aws_api_gateway_rest_api.orders_api.root_resource_id
  path_part   = "orders"
}

resource "aws_api_gateway_method" "post_orders" {
  rest_api_id   = aws_api_gateway_rest_api.orders_api.id
  resource_id   = aws_api_gateway_resource.orders.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "post_orders" {
  rest_api_id             = aws_api_gateway_rest_api.orders_api.id
  resource_id             = aws_api_gateway_resource.orders.id
  http_method             = aws_api_gateway_method.post_orders.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.create_order.invoke_arn
}

# /orders/{order_id}
resource "aws_api_gateway_resource" "order_by_id" {
  rest_api_id = aws_api_gateway_rest_api.orders_api.id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "{order_id}"
}

resource "aws_api_gateway_method" "get_order" {
  rest_api_id   = aws_api_gateway_rest_api.orders_api.id
  resource_id   = aws_api_gateway_resource.order_by_id.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "get_order" {
  rest_api_id             = aws_api_gateway_rest_api.orders_api.id
  resource_id             = aws_api_gateway_resource.order_by_id.id
  http_method             = aws_api_gateway_method.get_order.http_method
  integration_http_method = "POST" # Lambda proxy integrations are always POST
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.create_order.invoke_arn
}

resource "aws_lambda_permission" "apigw_invoke_create_order" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_order.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.orders_api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "orders_api" {
  rest_api_id = aws_api_gateway_rest_api.orders_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.orders.id,
      aws_api_gateway_method.post_orders.id,
      aws_api_gateway_integration.post_orders.id,
      aws_api_gateway_resource.order_by_id.id,
      aws_api_gateway_method.get_order.id,
      aws_api_gateway_integration.get_order.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.post_orders,
    aws_api_gateway_integration.get_order,
  ]
}

resource "aws_api_gateway_stage" "orders_api" {
  deployment_id = aws_api_gateway_deployment.orders_api.id
  rest_api_id   = aws_api_gateway_rest_api.orders_api.id
  stage_name    = var.environment

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_access_logs.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      ip               = "$context.identity.sourceIp"
      httpMethod       = "$context.httpMethod"
      path             = "$context.path"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integration.error"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gateway_access_logs" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
}
