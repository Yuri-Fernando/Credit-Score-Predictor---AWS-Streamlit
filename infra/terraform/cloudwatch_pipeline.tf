# ------------------------------------------------------------------ CloudWatch: pipeline (Step Functions) + dashboard
# Alarmes do pipeline só existem quando var.enable_pipeline_orchestration = true (os recursos
# que monitoram também são condicionais). O dashboard sempre existe e inclui o widget do
# pipeline só nesse caso — consistente com os alarmes RED de main.tf (Lambda predict / API).

resource "aws_cloudwatch_metric_alarm" "pipeline_executions_failed" {
  count               = var.enable_pipeline_orchestration ? 1 : 0
  alarm_name          = "${local.name}-pipeline-executions-failed"
  namespace           = "AWS/States"
  metric_name         = "ExecutionsFailed"
  dimensions          = { StateMachineArn = aws_sfn_state_machine.pipeline[0].arn }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "pipeline_executions_timed_out" {
  count               = var.enable_pipeline_orchestration ? 1 : 0
  alarm_name          = "${local.name}-pipeline-executions-timed-out"
  namespace           = "AWS/States"
  metric_name         = "ExecutionsTimedOut"
  dimensions          = { StateMachineArn = aws_sfn_state_machine.pipeline[0].arn }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "pipeline_step_errors" {
  for_each            = var.enable_pipeline_orchestration ? aws_lambda_function.pipeline_step : {}
  alarm_name          = "${local.name}-pipeline-${each.key}-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.value.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name}-operacional"
  dashboard_body = jsonencode({
    widgets = concat(
      [
        {
          type = "metric", x = 0, y = 0, width = 12, height = 6
          properties = {
            title  = "Lambda predict — invocações / erros / throttles"
            region = var.region
            metrics = [
              ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.predict.function_name, { stat = "Sum" }],
              ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.predict.function_name, { stat = "Sum" }],
              ["AWS/Lambda", "Throttles", "FunctionName", aws_lambda_function.predict.function_name, { stat = "Sum" }],
            ]
          }
        },
        {
          type = "metric", x = 12, y = 0, width = 12, height = 6
          properties = {
            title  = "Lambda predict — latência p95"
            region = var.region
            metrics = [
              ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.predict.function_name, { stat = "p95" }],
            ]
          }
        },
        {
          type = "metric", x = 0, y = 6, width = 12, height = 6
          properties = {
            title  = "API Gateway — 4xx / 5xx"
            region = var.region
            metrics = [
              ["AWS/ApiGateway", "4xx", "ApiId", aws_apigatewayv2_api.http.id, { stat = "Sum" }],
              ["AWS/ApiGateway", "5xx", "ApiId", aws_apigatewayv2_api.http.id, { stat = "Sum" }],
            ]
          }
        },
      ],
      var.enable_pipeline_orchestration ? [
        {
          type = "metric", x = 12, y = 6, width = 12, height = 6
          properties = {
            title  = "Pipeline (Step Functions) — execuções"
            region = var.region
            metrics = [
              ["AWS/States", "ExecutionsStarted", "StateMachineArn", aws_sfn_state_machine.pipeline[0].arn, { stat = "Sum" }],
              ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", aws_sfn_state_machine.pipeline[0].arn, { stat = "Sum" }],
              ["AWS/States", "ExecutionsFailed", "StateMachineArn", aws_sfn_state_machine.pipeline[0].arn, { stat = "Sum" }],
            ]
          }
        },
      ] : []
    )
  })
}
