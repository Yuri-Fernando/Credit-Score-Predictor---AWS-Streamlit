locals {
  name = "${var.project}-${var.environment}"
}

data "aws_caller_identity" "current" {}

# ------------------------------------------------------------------ KMS
resource "aws_kms_key" "main" {
  description             = "${local.name} — dados de inferência, artefatos e logs"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "main" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.main.key_id
}

# ------------------------------------------------------------------ S3 (artefatos de modelo)
resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name}-artifacts-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.main.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ------------------------------------------------------------------ DynamoDB (log de inferência)
resource "aws_dynamodb_table" "inference" {
  name         = "${local.name}-inference-log"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.main.arn
  }
}

# ------------------------------------------------------------------ SageMaker Model Registry + endpoint (opcional)
resource "aws_sagemaker_model_package_group" "pd" {
  model_package_group_name        = "${local.name}-riskcredit-pd-12m"
  model_package_group_description = "Champion/challenger do RiskCredit — aprovação manual obrigatória"
}

data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker" {
  name               = "${local.name}-sagemaker"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
}

data "aws_iam_policy_document" "sagemaker" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }
  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.main.arn]
  }
  statement {
    actions   = ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "logs:CreateLogStream", "logs:PutLogEvents", "logs:CreateLogGroup"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sagemaker" {
  role   = aws_iam_role.sagemaker.id
  policy = data.aws_iam_policy_document.sagemaker.json
}

resource "aws_sagemaker_model" "champion" {
  count              = var.create_endpoint ? 1 : 0
  name               = "${local.name}-champion"
  execution_role_arn = aws_iam_role.sagemaker.arn
  primary_container {
    image          = var.sagemaker_image
    model_data_url = var.champion_model_data_url
  }
}

resource "aws_sagemaker_model" "challenger" {
  count              = var.create_endpoint && var.canary_challenger_weight > 0 ? 1 : 0
  name               = "${local.name}-challenger"
  execution_role_arn = aws_iam_role.sagemaker.arn
  primary_container {
    image          = var.sagemaker_image
    model_data_url = var.challenger_model_data_url
  }
}

resource "aws_sagemaker_endpoint_configuration" "main" {
  count       = var.create_endpoint ? 1 : 0
  name_prefix = "${local.name}-"
  kms_key_arn = aws_kms_key.main.arn

  production_variants {
    variant_name           = "champion"
    model_name             = aws_sagemaker_model.champion[0].name
    initial_variant_weight = 1 - var.canary_challenger_weight
    serverless_config {
      max_concurrency   = 5
      memory_size_in_mb = 2048
    }
  }

  dynamic "production_variants" {
    for_each = var.canary_challenger_weight > 0 ? [1] : []
    content {
      variant_name           = "challenger"
      model_name             = aws_sagemaker_model.challenger[0].name
      initial_variant_weight = var.canary_challenger_weight
      serverless_config {
        max_concurrency   = 2
        memory_size_in_mb = 2048
      }
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "main" {
  count                = var.create_endpoint ? 1 : 0
  name                 = "${local.name}-pd"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.main[0].name
}

# ------------------------------------------------------------------ Lambda (menor privilégio)
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}-predict"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "WriteInferenceLog"
    actions   = ["dynamodb:PutItem", "dynamodb:BatchWriteItem"]
    resources = [aws_dynamodb_table.inference.arn]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
  statement {
    sid       = "Kms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.main.arn]
  }
  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
  dynamic "statement" {
    for_each = var.create_endpoint ? [1] : []
    content {
      sid       = "InvokeOnlyThisEndpoint"
      actions   = ["sagemaker:InvokeEndpoint"]
      resources = [aws_sagemaker_endpoint.main[0].arn]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "predict" {
  function_name                  = "${local.name}-predict"
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.11"
  handler                        = "Nuvem.lambda_function_v3.lambda_handler"
  filename                       = var.lambda_zip_path
  source_code_hash               = fileexists(var.lambda_zip_path) ? filebase64sha256(var.lambda_zip_path) : null
  timeout                        = 10
  memory_size                    = 1024
  reserved_concurrent_executions = 20
  kms_key_arn                    = aws_kms_key.main.arn

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      INFERENCE_MODE     = var.create_endpoint ? "sagemaker" : "local"
      SAGEMAKER_ENDPOINT = var.create_endpoint ? aws_sagemaker_endpoint.main[0].name : ""
      DYNAMODB_TABLE     = aws_dynamodb_table.inference.name
      PERSIST            = "true"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# ------------------------------------------------------------------ Autenticação (Cognito) + API Gateway HTTP
resource "aws_cognito_user_pool" "main" {
  name = "${local.name}-users"
  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }
}

resource "aws_cognito_user_pool_client" "api" {
  name                                 = "${local.name}-api"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = false
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  allowed_oauth_flows_user_pool_client = false
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.http.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito"
  jwt_configuration {
    audience = [aws_cognito_user_pool_client.api.id]
    issuer   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.predict.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "predict" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "POST /predict"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = var.api_throttle_rate
    throttling_burst_limit = var.api_throttle_burst
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId = "$context.requestId", status = "$context.status", latency = "$context.responseLatency",
      route     = "$context.routeKey", ip = "$context.identity.sourceIp", user = "$context.authorizer.claims.sub"
    })
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.predict.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

# ------------------------------------------------------------------ CloudWatch: alarmes RED
resource "aws_sns_topic" "alarms" {
  name              = "${local.name}-alarms"
  kms_master_key_id = aws_kms_key.main.id
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name}-lambda-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.predict.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.name}-lambda-throttles"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.predict.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "lambda_p95" {
  alarm_name          = "${local.name}-lambda-p95-latency"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = { FunctionName = aws_lambda_function.predict.function_name }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 3
  threshold           = 300
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name}-api-5xx"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.http.id, Stage = "$default" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}
