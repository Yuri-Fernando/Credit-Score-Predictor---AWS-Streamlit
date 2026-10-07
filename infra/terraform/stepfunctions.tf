# ------------------------------------------------------------------ Orquestração (Step Functions) — plano §5.1
# Desligado por padrão (var.enable_pipeline_orchestration = false): definição validada com
# `terraform validate`, NUNCA aplicada nesta sessão. Cada Task do state machine é uma Lambda
# dedicada que só chama funções locais em src/mlops/pipeline_steps.py — nenhuma acessa a AWS;
# o mesmo pacote (var.lambda_zip_path) da Lambda `predict` é reaproveitado, trocando o handler.

locals {
  pipeline_steps = {
    validate = "src.mlops.pipeline_steps.validate_batch"
    score    = "src.mlops.pipeline_steps.score_batch"
    combine  = "src.mlops.pipeline_steps.combine_shadow"
    monitor  = "src.mlops.pipeline_steps.monitor_drift"
    publish  = "src.mlops.pipeline_steps.publish_manifest"
  }
}

data "aws_iam_policy_document" "pipeline_lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "pipeline_lambda" {
  count              = var.enable_pipeline_orchestration ? 1 : 0
  name               = "${local.name}-pipeline-lambda"
  assume_role_policy = data.aws_iam_policy_document.pipeline_lambda_assume.json
}

resource "aws_cloudwatch_log_group" "pipeline_lambda" {
  for_each          = var.enable_pipeline_orchestration ? local.pipeline_steps : {}
  name              = "/aws/lambda/${local.name}-pipeline-${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn
}

data "aws_iam_policy_document" "pipeline_lambda" {
  count = var.enable_pipeline_orchestration ? 1 : 0
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [for lg in aws_cloudwatch_log_group.pipeline_lambda : "${lg.arn}:*"]
  }
  statement {
    sid       = "Kms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.main.arn]
  }
}

resource "aws_iam_role_policy" "pipeline_lambda" {
  count  = var.enable_pipeline_orchestration ? 1 : 0
  role   = aws_iam_role.pipeline_lambda[0].id
  policy = data.aws_iam_policy_document.pipeline_lambda[0].json
}

resource "aws_lambda_function" "pipeline_step" {
  for_each                       = var.enable_pipeline_orchestration ? local.pipeline_steps : {}
  function_name                  = "${local.name}-pipeline-${each.key}"
  role                           = aws_iam_role.pipeline_lambda[0].arn
  runtime                        = "python3.11"
  handler                        = each.value
  filename                       = var.lambda_zip_path
  source_code_hash               = fileexists(var.lambda_zip_path) ? filebase64sha256(var.lambda_zip_path) : null
  timeout                        = 30
  memory_size                    = 512
  reserved_concurrent_executions = 5
  kms_key_arn                    = aws_kms_key.main.arn

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      MODEL_PACKAGE_GROUP = "riskcredit-pd-12m"
    }
  }

  depends_on = [aws_cloudwatch_log_group.pipeline_lambda]
}

resource "aws_cloudwatch_log_group" "pipeline_sfn" {
  count             = var.enable_pipeline_orchestration ? 1 : 0
  name              = "/aws/vendedlogs/states/${local.name}-pipeline"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  count              = var.enable_pipeline_orchestration ? 1 : 0
  name               = "${local.name}-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}

data "aws_iam_policy_document" "sfn" {
  count = var.enable_pipeline_orchestration ? 1 : 0
  statement {
    sid       = "InvokeOnlyPipelineLambdas"
    actions   = ["lambda:InvokeFunction"]
    resources = [for fn in aws_lambda_function.pipeline_step : fn.arn]
  }
  statement {
    sid = "LoggingDelivery"
    actions = [
      "logs:CreateLogDelivery", "logs:GetLogDelivery", "logs:UpdateLogDelivery", "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries", "logs:PutResourcePolicy", "logs:DescribeResourcePolicies", "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }
  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sfn" {
  count  = var.enable_pipeline_orchestration ? 1 : 0
  role   = aws_iam_role.sfn[0].id
  policy = data.aws_iam_policy_document.sfn[0].json
}

# Definição real (ASL) em infra/terraform/templates/pipeline.asl.json.tftpl — mesmo arquivo
# usado pelos testes Python (tests/test_stepfunctions.py) para validar sintaxe e simular
# localmente a lógica de transição de estados, sem AWS.
resource "aws_sfn_state_machine" "pipeline" {
  count    = var.enable_pipeline_orchestration ? 1 : 0
  name     = "${local.name}-pipeline"
  role_arn = aws_iam_role.sfn[0].arn
  type     = "STANDARD"

  definition = templatefile("${path.module}/templates/pipeline.asl.json.tftpl", {
    validate_lambda_arn = aws_lambda_function.pipeline_step["validate"].arn
    score_lambda_arn    = aws_lambda_function.pipeline_step["score"].arn
    combine_lambda_arn  = aws_lambda_function.pipeline_step["combine"].arn
    monitor_lambda_arn  = aws_lambda_function.pipeline_step["monitor"].arn
    publish_lambda_arn  = aws_lambda_function.pipeline_step["publish"].arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.pipeline_sfn[0].arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tracing_configuration {
    enabled = true
  }
}
