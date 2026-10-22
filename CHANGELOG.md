# CHANGELOG — Credit Score Predictor (AWS + Streamlit)

Documento mestre de histórico. Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) + SemVer.

## [3.2.0] — 2026-10-21 — Governança de ciclo de vida no registry local

Origem: auditoria de portfólio (governança de modelos: dono, tier de risco, revisão periódica, retirada).
Restrição mantida: **nada foi aplicado na AWS**; o SageMaker Model Registry real continua pendente por custo.

### Added
- `src/mlops/registry.py` — camada de ciclo de vida **opcional** em cada versão (bloco `lifecycle`): campos
  `model_owner`, `business_owner`, `risk_tier` (`LOW`/`LIMITED`/`HIGH`/`PROHIBITED`), `approval_date`,
  `review_due_date`, `retired_at`; estágios `Validation → Registry → RiskAssessment → ManualApproval → Shadow →
  Canary → Production → DriftMonitoring → Revalidation → Retirement` com transições validadas (`advance()`,
  `InvalidTransition`), rollback Canary→Shadow e reabertura da aprovação em `Revalidation`.
- `set_owners()`, `assess_risk()`, `retire()`, `review_status()` e `overdue_reviews()`; exceções tipadas
  `LifecycleError`, `InvalidTransition`, `RiskAssessmentUnavailable`, `ReviewOverdue`.
- Revisão com vencimento: a aprovação agenda `review_due_date` (intervalo por tier); vencida, bloqueia promoção
  (`Shadow→Canary→Production`) e `deployment_manifest()`; o rollback não é bloqueado.
- Retirement terminal que **preserva** métricas, hashes e histórico (a versão sai de `latest_approved()` e não gera
  manifesto de deploy). Rejeição de versão governada também encerra a versão.
- `risk_tier` lido de um `risk_assessment.json` (RiskCredit v3.1) por caminho configurável em
  `configs/lifecycle_policy.yaml`, com conferência de `model_version` e registro de caminho + SHA-256 de origem.
- `configs/lifecycle_policy.yaml` e `load_lifecycle_policy()`.
- `tests/test_lifecycle.py` — 40 testes (transições, pré-condições, vencimento, revalidação, retirement, tier por
  arquivo, compatibilidade com manifesto anterior à v3.2).

### Changed
- `LocalModelRegistry.set_status`, `latest_approved` e `deployment_manifest` ganharam parâmetros/validações
  **opcionais** (`today`, `review_interval_days`); a assinatura anterior continua válida.
- Compatibilidade: versão sem bloco `lifecycle` (v3.0/v3.1) recebe o default inferido (não governado) e mantém o
  comportamento anterior até a primeira operação de ciclo de vida. Os 14 testes de `tests/test_mlops.py` seguem passando.

### Limitações
- `actor`/`approver` são texto livre (sem autenticação ou assinatura); datas dependem do relógio local.
- Não há integração com o SageMaker Model Registry real nem com um catálogo de dados.

## [3.1.0] — 2026-10-07 — Orquestração (Step Functions) + CloudWatch dashboard + guard-rails de custo

Origem: auditoria de portfólio, item B.8 ("Credit Score AWS — orchestration/monitoring/deploy").
Restrição mantida: **nenhum recurso novo foi criado/aplicado na AWS** — tudo abaixo é IaC
validado (`terraform validate`, nos dois valores de `enable_pipeline_orchestration`) e lógica
testada localmente, sem `plan`/`apply` reais.

### Added
- `src/mlops/pipeline_steps.py` — 5 steps do pipeline (validate → score champion/challenger →
  combine/shadow → monitor drift → publish manifest), funções puras JSON-in/JSON-out
  (compatíveis com handler de Lambda).
- `src/mlops/asl_runner.py` — interpretador local mínimo de Amazon States Language (Task,
  Parallel, Choice, Succeed, Fail, Catch) + `validate_structure()` (validação estrutural real:
  referências `Next`/`Default`/`Catch` órfãs, `Choice` sem `Default`, `Parallel` sem `Branches`).
- `src/mlops/shadow.py::shadow_compare_arrays` — mesma métrica de `shadow_compare`, mas a partir
  de PDs já calculadas (sem callables cruzando a fronteira JSON de uma Task real).
- `infra/terraform/templates/pipeline.asl.json.tftpl` — definição real (ASL) do state machine:
  `ValidateBatch → ScoreShadow (Parallel) → CombineShadow → MonitorDrift → Choice
  (rollback / hold-por-drift / hold-por-canary / promote → PublishManifest)`. Único arquivo-fonte,
  usado tanto pelo `templatefile()` do Terraform quanto pelos testes Python.
- `infra/terraform/stepfunctions.tf` — 5 Lambdas de step (mesmo zip de `predict`, handlers em
  `src/mlops/pipeline_steps.py`) + IAM de menor privilégio + `aws_sfn_state_machine` com logging
  (CloudWatch Logs, `level=ALL`) e X-Ray. Tudo atrás de `var.enable_pipeline_orchestration`
  (padrão `false`).
- `infra/terraform/cloudwatch_pipeline.tf` — alarmes `ExecutionsFailed`/`ExecutionsTimedOut` do
  state machine, alarme de erros por step Lambda, e `aws_cloudwatch_dashboard` operacional
  (Lambda predict, API Gateway, e o pipeline quando habilitado).
- `infra/terraform/cost_guardrails.tf` — `aws_budgets_budget` mensal (alerta em 80% real e 100%
  previsto) + `var.mandatory_tags` (tags obrigatórias via `default_tags`, com `validation` exigindo
  `CostCenter`/`Owner`).
- `scripts/terraform_guard.sh` — único caminho suportado para operar o Terraform desta fase:
  `fmt`/`validate`/`plan` liberados; `apply`/`destroy` bloqueados a menos que
  `TF_GUARD_ALLOW_APPLY=yes-eu-entendo-o-custo` seja definido explicitamente (mesmo padrão do
  ArgusAI / Enterprise Cloud Automation Platform).
- `tests/test_stepfunctions.py` (13 testes): sintaxe/estrutura real do ASL pós-substituição dos
  placeholders, simulação local ponta-a-ponta (validate→score→shadow→drift, dados reais —
  golden samples + registry aprovado, sem mutar `registry/model_registry.json`), e os 4 ramos do
  `Choice` isolados (rollback / hold-drift / hold-canary / publish com manifesto real / publish
  sem versão aprovada → reject).

### Limitação documentada (achado real, não um bug do teste)
- O monitoramento de drift do score (PSI) fica "vermelho" para **qualquer** lote sintético
  disponível no repositório (golden samples — casos de borda — ou amostragem independente por
  feature do perfil de referência), porque nenhum reproduz a estrutura conjunta real do treino.
  O teste ponta-a-ponta reflete esse resultado real (`HoldForDriftReview`) em vez de forçar um
  "caminho feliz" artificial; os 4 ramos de decisão são testados isoladamente a partir do estado
  `CheckCanaryAndDrift`. Mitigação real (tráfego de produção de verdade) fica no ROADMAP.

### Não alterado
- `Nuvem/lambda_function.py` (v1), `Nuvem/lambda_function_v3.py` (v3, handler único), `App/`,
  recursos na conta AWS. `var.create_endpoint` continua `false`.

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
