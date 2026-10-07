# ROADMAP — Credit Score Predictor

Legenda: ✅ feito (local) · ⏸️ pendente por custo (exige conta AWS) · ⏳ planejado

| Item (plano §5) | Estado | Próximo passo quando houver orçamento |
|---|---|---|
| 5.1 IaC | ✅ código validado (`terraform validate`, com e sem `enable_pipeline_orchestration`) · ⏸️ apply | `terraform plan` (via `scripts/terraform_guard.sh plan`) em conta de staging com orçamento/alertas de billing; manter `create_endpoint=false` e `enable_pipeline_orchestration=false` até terem orçamento aprovado |
| 5.1b Step Functions | ✅ ASL real (`infra/terraform/templates/pipeline.asl.json.tftpl`) + 5 Lambdas de step + simulação local de transição (`tests/test_stepfunctions.py`, 13 testes) · ⏸️ execução real | ligar `enable_pipeline_orchestration=true`, `terraform plan`, revisar custo (Standard workflow cobra por transição) antes de `apply`; resolver a limitação de drift (ver CHANGELOG 3.1.0) com tráfego real antes de confiar no gate em produção |
| 5.1c CloudWatch dashboard/alarmes do pipeline | ✅ definidos (`infra/terraform/cloudwatch_pipeline.tf`) · ⏸️ apply | aplicar junto com 5.1b; dashboard sempre existe (Lambda predict/API), widget do pipeline só quando `enable_pipeline_orchestration=true` |
| 5.1d Guard-rails de custo | ✅ `aws_budgets_budget` + `mandatory_tags` (CostCenter/Owner obrigatórios) + `scripts/terraform_guard.sh` (apply bloqueado sem `TF_GUARD_ALLOW_APPLY`) | definir `budget_alert_email` real antes do apply; revisar `monthly_budget_usd` (padrão USD 10) |
| 5.2 Model Registry | ✅ local (semântica SageMaker) · ⏸️ real | `create_model_package` no group do IaC; aprovação via `update_model_package` |
| 5.3 CI/CD | ✅ PR: testes + contrato + IaC validate · ⏸️ release | job de release: empacotar Lambda v3, `terraform plan`, deploy staging, smoke test, aprovação manual, prod (OIDC GitHub→AWS, sem chaves) |
| 5.4 Canary / shadow | ✅ avaliação offline + política · ⏸️ tráfego real | variantes champion/challenger no endpoint (já no IaC), pesos 10→50→100 conforme `configs/canary_policy.yaml` |
| 5.5 Monitoring | ✅ offline (PSI, RED do log) · ⏸️ CloudWatch/X-Ray | alarmes do IaC + SageMaker Model Monitor com data capture; job agendado de drift sobre o DynamoDB |
| 5.6 Data quality | ✅ contrato bloqueante no handler | — |
| 5.7 Segurança | ✅ handler (limites, erros tipados, logs sem dado) · ✅ IaC (Cognito JWT, throttling, KMS, IAM mínimo) · ⏸️ apply | WAF exige REST API ou CloudFront; Secrets Manager para qualquer segredo futuro; rotação da Lambda v1 para v3 |
| 5.8 Integração RiskCredit | ✅ contrato + paridade | automatizar sync do artefato por release do RiskCredit |
| Streamlit consumindo a API v3 com autenticação | ⏳ | trocar URL fixa da API v1 por variável de ambiente + login Cognito |
| Retirar credenciais locais do diretório de trabalho | ⏳ | mover `credenciais aws cli.txt` para o AWS CLI profile / SSO (arquivo já é ignorado pelo Git) |
