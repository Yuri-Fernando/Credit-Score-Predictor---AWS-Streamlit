# ROADMAP — Credit Score Predictor

Legenda: ✅ feito (local) · ⏸️ pendente por custo (exige conta AWS) · ⏳ planejado

| Item (plano §5) | Estado | Próximo passo quando houver orçamento |
|---|---|---|
| 5.1 IaC | ✅ código validado · ⏸️ apply | `terraform plan` em conta de staging com orçamento/alertas de billing; manter `create_endpoint=false` até o passo 5.2 |
| 5.2 Model Registry | ✅ local (semântica SageMaker) · ⏸️ real | `create_model_package` no group do IaC; aprovação via `update_model_package` |
| 5.3 CI/CD | ✅ PR: testes + contrato + IaC validate · ⏸️ release | job de release: empacotar Lambda v3, `terraform plan`, deploy staging, smoke test, aprovação manual, prod (OIDC GitHub→AWS, sem chaves) |
| 5.4 Canary / shadow | ✅ avaliação offline + política · ⏸️ tráfego real | variantes champion/challenger no endpoint (já no IaC), pesos 10→50→100 conforme `configs/canary_policy.yaml` |
| 5.5 Monitoring | ✅ offline (PSI, RED do log) · ⏸️ CloudWatch/X-Ray | alarmes do IaC + SageMaker Model Monitor com data capture; job agendado de drift sobre o DynamoDB |
| 5.6 Data quality | ✅ contrato bloqueante no handler | — |
| 5.7 Segurança | ✅ handler (limites, erros tipados, logs sem dado) · ✅ IaC (Cognito JWT, throttling, KMS, IAM mínimo) · ⏸️ apply | WAF exige REST API ou CloudFront; Secrets Manager para qualquer segredo futuro; rotação da Lambda v1 para v3 |
| 5.8 Integração RiskCredit | ✅ contrato + paridade | automatizar sync do artefato por release do RiskCredit |
| Streamlit consumindo a API v3 com autenticação | ⏳ | trocar URL fixa da API v1 por variável de ambiente + login Cognito |
| Retirar credenciais locais do diretório de trabalho | ⏳ | mover `credenciais aws cli.txt` para o AWS CLI profile / SSO (arquivo já é ignorado pelo Git) |
