# IaC do Credit Score Predictor — NÃO APLICADO (deploy pausado por custo).
# Validado com `terraform validate`; nenhum `plan`/`apply` foi executado contra uma conta AWS.
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  # backend "s3" {  # habilitar só quando houver conta/estado remoto definidos
  #   bucket = "<tfstate-bucket>"
  #   key    = "credit-score/terraform.tfstate"
  #   region = "sa-east-1"
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = merge(var.mandatory_tags, { Project = var.project, Environment = var.environment })
  }
}
