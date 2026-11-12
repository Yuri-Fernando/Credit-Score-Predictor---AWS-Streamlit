# IaC do Credit Score Predictor. Aplicado, testado e destruído numa conta AWS real (lab Free Plan) em 2026-11-11.
# Sem backend remoto de propósito: o state fica local (nenhum dado persistido na conta de laboratório).
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
