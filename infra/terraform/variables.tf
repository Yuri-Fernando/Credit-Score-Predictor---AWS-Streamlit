variable "project" {
  type    = string
  default = "credit-score"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "lambda_zip_path" {
  description = "Pacote da Lambda v3 (src/mlops + model_artifacts). Gerado pelo CI."
  type        = string
  default     = "../../dist/lambda_v3.zip"
}

variable "create_endpoint" {
  description = "Cria endpoint SageMaker (custo por hora). Mantido false por padrão."
  type        = bool
  default     = false
}

variable "sagemaker_image" {
  description = "Imagem do container XGBoost do SageMaker na região."
  type        = string
  default     = "737474898029.dkr.ecr.sa-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"
}

variable "champion_model_data_url" {
  type    = string
  default = "s3://placeholder/champion/model.tar.gz"
}

variable "challenger_model_data_url" {
  type    = string
  default = ""
}

variable "canary_challenger_weight" {
  description = "Peso de tráfego do challenger (0 = sem canary). Segue configs/canary_policy.yaml."
  type        = number
  default     = 0
}

variable "api_throttle_rate" {
  type    = number
  default = 20
}

variable "api_throttle_burst" {
  type    = number
  default = 40
}

variable "log_retention_days" {
  type    = number
  default = 30
}
