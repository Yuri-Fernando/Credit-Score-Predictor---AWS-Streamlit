# CHANGELOG — Credit Score Predictor (AWS + Streamlit)

Documento mestre de histórico. Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) + SemVer.

## [3.0.0] — 2026-09-28 — MLOps financeiro (local-first)

Origem: plano de evolução do portfólio financeiro, seção 5. Restrição do dono do projeto: **não alterar a
infraestrutura AWS por custo** — tudo abaixo roda local; o que exige a conta ficou no ROADMAP.

### Added
- `model_artifacts/riskcredit-v3/` — contrato do champion publicado pelo RiskCredit v3.0.2.
- `src/mlops/` — `features.py`, `contract.py`, `scoring.py`, `registry.py`, `monitoring.py`, `shadow.py`, `handler.py`.
- `Nuvem/lambda_function_v3.py` — entrypoint da Lambda v3 (não implantado).
- `configs/canary_policy.yaml`, `scripts/mlops_demo.py`, `registry/model_registry.json`, `reports/mlops/`.
- `infra/terraform/` — IaC validado (`terraform validate`), **não aplicado**; endpoint SageMaker desligado por padrão.
- `tests/test_mlops.py` (14 testes) e CI com testes + `terraform fmt/validate`.
- `requirements-mlops.txt`.

### Não alterado
- `Nuvem/lambda_function.py` (v1 em produção), `App/`, recursos na conta AWS.

## [2.0.0] — 2026-09-10 — Adversarial Robustness & Model Security
- `src/adversarial/` (evasão, curvas de robustez, adversarial training, model extraction), notebook e 6 testes.

## [1.0.0] — 2025-08-13
- Lambda + API Gateway + SageMaker (XGBoost) + DynamoDB + S3 + Streamlit.
