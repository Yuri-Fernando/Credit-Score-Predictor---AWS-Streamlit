# ------------------------------------------------------------------ Guard-rails de custo (plano §5.1/5.3)
# 1) var.enable_pipeline_orchestration / var.create_endpoint: recursos de custo não-trivial
#    (Step Functions + 5 Lambdas / endpoint SageMaker) ficam desligados por padrão — quem
#    quiser ver o plan precisa ligar explicitamente a flag, e mesmo assim só `plan`/`validate`
#    são suportados nesta sessão (ver scripts/terraform_guard.sh).
# 2) aws_budgets_budget: alarme de orçamento mensal, sempre definido (orçamento em si não tem custo).
# 3) var.mandatory_tags (versions.tf): tags obrigatórias via provider default_tags, com
#    validação de que CostCenter/Owner estão presentes.

variable "monthly_budget_usd" {
  description = "Teto mensal (USD) para o guard-rail de custo (AWS Budgets)."
  type        = number
  default     = 10
  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd precisa ser maior que zero."
  }
}

variable "budget_alert_email" {
  description = "E-mail para alerta do AWS Budgets ao atingir 80% do orçamento. Vazio = só notificação por SNS (aws_sns_topic.alarms, 100% previsto)."
  type        = string
  default     = ""
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = var.budget_alert_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 80
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_alert_email]
    }
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.alarms.arn]
  }
}
