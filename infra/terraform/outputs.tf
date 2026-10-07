output "api_endpoint" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "model_package_group" {
  value = aws_sagemaker_model_package_group.pd.model_package_group_name
}

output "inference_table" {
  value = aws_dynamodb_table.inference.name
}

output "sagemaker_endpoint" {
  value = var.create_endpoint ? aws_sagemaker_endpoint.main[0].name : "not-created (create_endpoint=false)"
}

output "pipeline_state_machine_arn" {
  value = var.enable_pipeline_orchestration ? aws_sfn_state_machine.pipeline[0].arn : "not-created (enable_pipeline_orchestration=false)"
}

output "monthly_budget_name" {
  value = aws_budgets_budget.monthly.name
}
