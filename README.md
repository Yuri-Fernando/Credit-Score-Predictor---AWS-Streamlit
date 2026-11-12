# 💳 Credit Score Predictor — AWS + Streamlit — de inferência serverless a MLOps financeiro orquestrado e governado

### Python · AWS Lambda · SageMaker · API Gateway · DynamoDB · S3 · Step Functions · Terraform · XGBoost · Streamlit

[![ci](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit/actions/workflows/ci.yml/badge.svg)](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit/actions/workflows/ci.yml)
![testes](https://img.shields.io/badge/testes-73%20passed-0a8a0a)
![IaC](https://img.shields.io/badge/IaC-aplicado%20na%20AWS%20real%20(lab)-ff9900)
![versão](https://img.shields.io/badge/vers%C3%A3o-v3.3.0-4a5563) ![license](https://img.shields.io/badge/license-sem%20arquivo-4a5563)

## Status

🟢 **Concluído no escopo v1 (fluxo serverless real) — v3.3.0: o Terraform da v3 foi aplicado numa conta AWS real (Free Plan, us-east-1) em 11/11/2026, validado de ponta a ponta e destruído no mesmo dia.**

A v1 (Lambda + API Gateway + SageMaker + DynamoDB + S3 + Streamlit) foi o fluxo real implantado em 2025. As v2/v3/v3.1/v3.2 (robustez adversarial, MLOps financeiro, orquestração via Step Functions, CloudWatch, guard-rails de custo e governança de ciclo de vida) foram desenvolvidas e testadas localmente (73 testes). Na v3.3.0 o `infra/terraform` saiu do `validate` para um **`apply` real** (30 recursos: API Gateway com JWT/Cognito, Lambda v3, DynamoDB, KMS, S3, alarmes) dentro da plataforma [AWS-Project](https://github.com/Yuri-Fernando/AWS-Project): a Lambda respondeu HTTP 200 com o modelo v3 e gravou a inferência no DynamoDB; em seguida, `terraform destroy` (30 destruídos). O endpoint SageMaker e o Step Functions ficaram desligados (custo por hora).

| Camada | Estado | Evidência |
|---|---|---|
| v1 — Lambda/API Gateway/SageMaker/DynamoDB/S3/Streamlit | 🟢 Real, implantado na AWS | Fluxo em produção desde 2025 |
| v2 — Robustez adversarial (proxy local) | 🟢 Local, testado | 6 testes (`tests/test_adversarial.py`) |
| v3 — MLOps financeiro (registry, contrato, drift, shadow/canary) | 🟢 Local, testado · IaC validado | 14 testes (`tests/test_mlops.py`) |
| v3.1 — Orquestração (Step Functions), CloudWatch, guard-rails de custo | 🟢 Local, testado · IaC validado | 13 testes (`tests/test_stepfunctions.py`) |
| v3.2 — Governança de ciclo de vida no registry (responsáveis, `risk_tier`, revisão com vencimento, Retirement) | 🟢 Local, testado | 40 testes (`tests/test_lifecycle.py`) |
| v3.3 — `infra/terraform` aplicado na AWS real (lab, Free Plan) | 🟢 Apply → teste → destroy em 11/11/2026 | Lambda HTTP 200 (modelo `v3-20260929`), registro no DynamoDB; [evidência](https://github.com/Yuri-Fernando/AWS-Project/blob/main/docs/evidence/aws/aws-inventory.png) |

---

## Descrição / Contexto

Aplicação de predição de risco de crédito estruturada em uma arquitetura serverless na AWS, integrando AWS Lambda, API Gateway, SageMaker, DynamoDB, S3 e Streamlit. O sistema recebe dados de um cliente, encaminha a requisição para uma função AWS Lambda e utiliza um modelo XGBoost hospedado no SageMaker para realizar a inferência; o resultado retorna para a aplicação e pode ser registrado no DynamoDB.

A partir da v2, o projeto deixou de ser só "deploy AWS" e passou a tratar o modelo de crédito como um sistema que precisa ser atacado, versionado, monitorado e orquestrado — sempre com a restrição explícita do autor de **não aplicar infraestrutura nova na conta por custo**.

---

## 🧭 Origem do Projeto

A v1 nasceu como demonstração de inferência de ML em produção serverless (Lambda, API Gateway, SageMaker). As versões seguintes vieram de uma auditoria de portfólio que apontou lacunas de maturidade:

1. Um modelo financeiro em produção sem teste de robustez adversarial é um risco não medido — levou à v2 (evasão de perturbação mínima, model extraction, adversarial training, tudo sobre um proxy local para não depender do endpoint real).
2. Um modelo que não é retreinado, revalidado e re-registrado com governança não é "MLOps", é um artefato estático — levou à v3 (contrato de dados, registry com aprovação manual, handler endurecido, monitoramento de drift, shadow/canary).
3. Um pipeline de MLOps sem orquestração real e sem guard-rail de custo é arriscado de aplicar numa conta pessoal — levou à v3.1 (Step Functions real via ASL, CloudWatch dashboard/alarmes, `aws_budgets_budget` e `scripts/terraform_guard.sh` bloqueando `apply`/`destroy` sem flag explícita).

Cada fase manteve o gate: **código e testes primeiro, infraestrutura validada depois, apply somente quando houver orçamento aprovado** (ver ROADMAP.md).

---

## 🎯 Objetivo

- Demonstrar inferência de ML em produção via arquitetura serverless (Lambda, API Gateway, SageMaker, DynamoDB, S3, Streamlit);
- Medir robustez adversarial do modelo de risco de crédito com ataques de evasão e extração de modelo;
- Implementar uma esteira de MLOps financeiro (contrato de dados, registry com gates, handler endurecido, monitoramento de drift, shadow/canary) executável sem AWS;
- Orquestrar esse pipeline com Step Functions (ASL real) e um interpretador local equivalente, sem depender de execução real na AWS;
- Aplicar guard-rails de custo (budget, tags obrigatórias, bloqueio de `apply`/`destroy`) antes de qualquer decisão de implantação real;
- Documentar honestamente o que foi testado localmente versus o que depende de orçamento aprovado.

---

## 🏗️ Arquitetura

### Sistema (v1 — real, em produção)

```text
Streamlit
    ↓
API Gateway  (POST /predict)
    ↓
AWS Lambda
    ↓
SageMaker Endpoint (XGBoost)
    ↓
Prediction / Score
    ↓
DynamoDB (log) · S3 (features)
```

### Pipeline de MLOps (v3/v3.1 — local-first, IaC validado e não aplicado)

```text
RiskCredit (treino, validação) ──contrato──▶ Registry local ──aprovação manual──▶ manifesto de deploy
                                                   │                                   (applied=false)
                                                   ▼
                          Handler v3 (validação → features → score → log) ──▶ monitoramento / shadow / canary
                                                   │
                                                   ▼
        Step Functions (ASL real) / asl_runner.py local:
        ValidateBatch → ScoreShadow [Parallel: champion/challenger] → CombineShadow →
        MonitorDrift → Choice (rollback / hold-drift / hold-canary / promote) → PublishManifest
                                                   │
                                                   ▼
                 CloudWatch (alarmes + dashboard) · AWS Budgets · terraform_guard.sh
```

### Módulos

| Módulo | Função | Teste |
|---|---|---|
| `Nuvem/lambda_function.py` | Handler v1, em produção real | Fluxo real na AWS |
| `src/adversarial/` | Evasão, curvas de robustez, adversarial training, model extraction | `tests/test_adversarial.py` (6) |
| `src/mlops/contract.py` | Contrato de dados — rejeita campo ausente/extra/fora de faixa | `tests/test_mlops.py` |
| `src/mlops/registry.py` | Model Registry (semântica SageMaker), gates de Gini/ECE/PSI | `tests/test_mlops.py` |
| `src/mlops/handler.py` | Handler v3 endurecido (limites, erros tipados, logs sem payload bruto) | `tests/test_mlops.py` |
| `src/mlops/monitoring.py` | PSI por feature e do score contra o perfil de treino | `tests/test_mlops.py` |
| `src/mlops/shadow.py` | Canary/shadow — concordância, PSI de score, Spearman | `tests/test_mlops.py` |
| `src/mlops/pipeline_steps.py` + `asl_runner.py` | Steps puros do pipeline + interpretador local de ASL | `tests/test_stepfunctions.py` (13) |
| `infra/terraform/` | IaC completo (Lambda, API Gateway, Step Functions, CloudWatch, budgets) | `terraform validate` (não aplicado) |
| `scripts/terraform_guard.sh` | Guard-rail: `apply`/`destroy` bloqueados sem `TF_GUARD_ALLOW_APPLY` | Uso manual documentado |

---

## ⚙️ Funcionamento

### Fluxo de predição (v1, real)

1. Usuário informa os dados no Streamlit;
2. Streamlit cria o payload e chama `POST /predict` no API Gateway;
3. API Gateway invoca a Lambda;
4. Lambda consulta o endpoint SageMaker (XGBoost);
5. Lambda recebe o score e registra no DynamoDB;
6. API retorna a resposta; Streamlit apresenta o resultado.

### Fluxo do pipeline MLOps (v3.1, local)

```text
1. Contrato valida o lote (campo ausente/extra/fora de faixa → rejeita)
2. ScoreShadow roda champion e challenger em paralelo
3. CombineShadow compara concordância, PSI de score, Spearman
4. MonitorDrift calcula PSI por feature e do score contra o perfil de treino
5. Choice decide: rollback / hold-por-drift / hold-por-canary / promote
6. PublishManifest grava o manifesto (applied=false, nunca toca a conta AWS)
```

### Governança de ciclo de vida do modelo (v3.2, local)

O registry (`src/mlops/registry.py`) ganhou uma camada **opcional** de ciclo de vida sobre a aprovação manual que já existia. É governança de apoio e trilha de auditoria — não um sistema de conformidade certificado, e nada disso é aplicado na AWS.

```text
Validation → Registry → RiskAssessment → ManualApproval → Shadow → Canary → Production → DriftMonitoring
                              ▲                              ▲        │                          │
                              │                              └────────┘ rollback do canary       ▼
                              └──────────────────────── Revalidation ◄──────────────────────────┘
qualquer estágio ativo → Retirement  (terminal; nada é apagado)
```

- **Campos novos** (bloco `lifecycle` de cada versão): `model_owner`, `business_owner`, `risk_tier` (`LOW`/`LIMITED`/`HIGH`/`PROHIBITED`), `approval_date`, `review_due_date`, `retired_at`. Padrão `None`; versões e manifestos anteriores à v3.2 continuam válidos e não mudam de comportamento até a primeira operação de ciclo de vida.
- **Transições** só pelo grafo acima (`advance()`); pular estágio levanta `InvalidTransition`. Cada passo exige `actor` e motivo (≥ 10 caracteres) e entra no `history` (append-only).
- **Pré-condições:** `ManualApproval` exige `risk_tier` (e `PROHIBITED` só admite `Retirement`); `Shadow` exige decisão `Approved`, os dois responsáveis e revisão agendada.
- **Revisão com vencimento:** a aprovação agenda `review_due_date = approval_date + intervalo do tier` (`HIGH` 90, `LIMITED` 180, `LOW` 365 dias, em `configs/lifecycle_policy.yaml`). Vencida, **bloqueia promoção** (`Shadow→Canary→Production`) e `deployment_manifest()` com `ReviewOverdue`; o rollback não é bloqueado e `overdue_reviews()` lista o que precisa revalidar.
- **Revalidation** reabre a aprovação (status volta a `PendingManualApproval`, tier é reavaliado) e preserva a decisão anterior no histórico.
- **Retirement** é terminal e não apaga a versão: métricas, hashes e histórico permanecem; a versão sai de `latest_approved()` e não gera manifesto de deploy.
- **`risk_tier` vindo do RiskCredit:** sem tier explícito, `assess_risk()` lê o `risk_assessment.json` do RiskCredit v3.1 pelo caminho configurado em `configs/lifecycle_policy.yaml`, confere que a avaliação é da mesma `model_version` do registry e grava caminho + SHA-256 + versão como origem. Arquivo ausente, ilegível ou de outra versão → `RiskAssessmentUnavailable` (sem tier "padrão" inventado).

```python
from datetime import date
from src.mlops.registry import LocalModelRegistry, load_lifecycle_policy

reg = LocalModelRegistry("registry/model_registry.json", policy=load_lifecycle_policy("configs/lifecycle_policy.yaml"))
pkg = reg.register("riskcredit-pd", "model_artifacts/riskcredit-v3")       # gates de validação → Registry
reg.set_owners("riskcredit-pd", 1, "modelagem", "risco-de-credito", actor="ana")
reg.advance("riskcredit-pd", 1, "RiskAssessment", "ana", "iniciar avaliação de risco do champion")
reg.assess_risk("riskcredit-pd", 1, "ana")                                 # tier lido do RiskCredit v3.1
reg.advance("riskcredit-pd", 1, "ManualApproval", "ana", "tier definido, pronto para decisão")
reg.set_status("riskcredit-pd", 1, "Approved", "revisor", "gates e risco revisados")  # agenda a revisão
reg.advance("riskcredit-pd", 1, "Shadow", "ana", "iniciar comparação champion x challenger")
```

---

## 🧠 Verificação / Validação

| Camada | O que prova | Resultado |
|---|---|---|
| `tests/test_adversarial.py` (6) | Evasão de perturbação mínima funciona sobre features manipuláveis reais, não idade/sexo | 6 passed |
| `tests/test_mlops.py` (14) | Contrato rejeita dado inválido; registry aplica gates; handler responde 400/413/422/500 corretamente | 14 passed |
| `tests/test_stepfunctions.py` (13) | ASL real é estruturalmente válido; simulação local ponta-a-ponta reflete o resultado real de drift; os 4 ramos do `Choice` são testados isoladamente | 13 passed |
| Paridade RiskCredit ↔ handler v3 | Mesma engenharia de features que o modelo de origem | máx \|Δ PD\| = 5e-7 nas 25 golden samples |
| `terraform validate` (com e sem `enable_pipeline_orchestration`) | IaC é sintaticamente e estruturalmente válido | Validado (v3.1) |
| `terraform plan`/`apply`/`destroy` na AWS real (11/11/2026) | O IaC cria a stack de verdade e a Lambda serve o modelo v3 atrás do API Gateway | 30 recursos criados; `lambda invoke` HTTP 200, PD 0,235, faixa D; DynamoDB 1 → 2 registros; 30 destruídos |

Execução nesta revisão: `python -m pytest -q tests` → **72 passed, 1 skipped** em 524 s (cópia local fora do Drive); o teste pulado (`test_real_riskcredit_assessment_if_present`) lê o `risk_assessment.json` real do RiskCredit v3.1 e só roda com a pasta do RiskCredit ao lado deste repo — rodado à parte no local original: **1 passed**. Total **73** (6 + 14 + 13 + 40).

---

## 🧪 Desenvolvimento Experimental

**Achado honesto, não um bug de teste:** o monitoramento de drift do score (PSI) fica "vermelho" para **qualquer** lote sintético disponível no repositório — tanto golden samples (casos de borda) quanto amostragem independente por feature do perfil de referência.

- **Hipótese inicial:** um lote amostrado do próprio perfil de treino deveria aparecer como "sem drift" (PSI baixo) no monitoramento.
- **O que se testou:** `src/mlops/monitoring.py` mede PSI por feature e do score; o teste ponta-a-ponta (`tests/test_stepfunctions.py`) roda esse cálculo sobre lotes sintéticos reais do repositório, sem mockar o resultado.
- **Causa real:** a amostragem independente por feature preserva as marginais de cada variável, mas destrói a estrutura conjunta (correlação entre features) que existia no treino real — é exatamente esse tipo de drift estrutural que o PSI por feature não detecta, mas o PSI do score detecta.
- **Decisão de design (drift):** em vez de forçar um "caminho feliz" artificial, o teste ponta-a-ponta reflete esse resultado real — o pipeline suspende a publicação em `HoldForDriftReview`. Os 4 ramos de decisão (rollback / hold-drift / hold-canary / promote) são testados isoladamente a partir do estado `CheckCanaryAndDrift`, para não depender só do caminho que o lote sintético disponível força. A mitigação real (tráfego de produção de verdade em vez de dados sintéticos) fica documentada no ROADMAP.

**Achados do primeiro `apply` real (v3.3.0)** — nenhum aparecia em `validate` nem no emulador:

| Sintoma | Causa real | Correção |
|---|---|---|
| `CreateLogGroup` → `AccessDeniedException` ("The specified KMS key does not exist or is not allowed") | a chave KMS não tinha key policy liberando o serviço CloudWatch Logs | `data.aws_iam_policy_document.kms` com `logs.<região>.amazonaws.com` e condição no ARN do log group |
| Lambda com `reserved_concurrent_executions = 20` | contas novas têm limite de 10 execuções e a AWS exige 10 não reservadas | variável `lambda_reserved_concurrency` (padrão 20; `-1` = sem reserva) |
| Chave KMS com 30 dias de janela de exclusão | laboratório precisa desmontar rápido | variável `kms_deletion_window_days` (padrão 30; 7 no lab) — chave pendente de exclusão não é cobrada |

---

## 🛠️ Tecnologias

- **Linguagem:** Python
- **Machine Learning:** XGBoost, scikit-learn (`HistGradientBoostingClassifier` como proxy local)
- **AWS (v1, real):** Lambda, API Gateway, SageMaker, DynamoDB, S3
- **AWS (v3, aplicado em lab real em 11/11/2026):** API Gateway HTTP + JWT/Cognito, Lambda, DynamoDB, KMS, S3, CloudWatch, AWS Budgets, IAM
- **AWS (v3.1, IaC validado, não aplicado — custo por hora):** Step Functions, endpoint SageMaker
- **IaC:** Terraform (`validate`/`plan`; `apply`/`destroy` em lab controlado)
- **Front-end:** Streamlit
- **Qualidade:** pytest, CI (GitHub Actions)

---

## 📊 Resultados

| Métrica | Valor | Origem |
|---|---|---|
| Testes totais | 73 passed (72 na suíte completa + 1 dependente do RiskCredit local) | `python -m pytest -q tests`, executado nesta sessão |
| Paridade RiskCredit vs handler v3 | máx \|Δ PD\| = 5e-7 | 25 golden samples, `scripts/mlops_demo.py` |
| Registry | Pacote aprovado por gates (Gini ≥ 0,45, ECE ≤ 0,02, PSI < 0,10) | `scripts/mlops_demo.py` |
| Drift — lote estável amostrado do perfil | 28/28 features verdes; score vermelho (PSI 0,67) | `scripts/mlops_demo.py`, ver achado acima |
| Drift — tráfego sintético V2 | 29/29 vermelhos | `scripts/mlops_demo.py` |
| Shadow — challenger V2 | Concordância 86%, PSI de score 0,85, Spearman 0,43 → canary **hold** | `scripts/mlops_demo.py` |
| IaC | `terraform validate` ok nos dois valores de `enable_pipeline_orchestration` | `scripts/terraform_guard.sh validate` |

| Apply real (v3.3.0) | 30 recursos criados e destruídos; Lambda HTTP 200, modelo `v3-20260929`, PD 0,235 (faixa D); DynamoDB 1 → 2 | `terraform apply`/`destroy` + `aws lambda invoke` em 11/11/2026 |

As linhas de testes, drift e shadow vêm de execuções locais (`pytest`, `scripts/mlops_demo.py`); só a linha "Apply real" vem da conta AWS (laboratório Free Plan, desmontado no mesmo dia).

---

## ☁️ Execução na AWS real (v3.3.0 — 11/11/2026)

O `infra/terraform` foi aplicado numa conta AWS **Free Plan** (us-east-1) como parte da plataforma
[AWS-Project](https://github.com/Yuri-Fernando/AWS-Project) (sessão R4), testado e destruído no mesmo dia.

**O que subiu (30 recursos):** API Gateway HTTP com autorizador JWT (Cognito User Pool + client), Lambda
`credit-score-lab-predict` (Python 3.11, 1024 MB, X-Ray, handler v3), DynamoDB `credit-score-lab-inference-log`
(PITR, KMS), bucket S3 de artefatos (versionado, KMS, acesso público bloqueado), chave KMS com rotação, log groups
criptografados, 4 alarmes CloudWatch + dashboard, tópico SNS, role/policies de IAM e SageMaker Model Package Group.
**Desligados de propósito (custo por hora):** endpoint SageMaker (`create_endpoint = false`) e Step Functions
(`enable_pipeline_orchestration = false`).

| Etapa | Comando | Resultado |
|---|---|---|
| Plano | `terraform plan -var-file=lab.tfvars` | 30 a criar |
| Apply | `terraform apply` | falhou no 1º apply (KMS × CloudWatch Logs) → corrigido → 12 criados + 1 alterado |
| Inferência | `aws lambda invoke` com payload de 23 features | HTTP 200, modelo `v3-20260929`, PD **0,235**, faixa **D** |
| Persistência | `dynamodb scan --select COUNT` antes/depois | 1 → 2 registros |
| Contrato | `contracts/scoring_result.v1` (validado pelo e2e do AWS-Project) | válido |
| Destroy | `terraform destroy` | **30 destruídos**; chave KMS em exclusão agendada (7 dias, sem cobrança) |

**Custo:** Lambda, API Gateway, DynamoDB e Cognito ficaram no free tier; KMS US$ 0,001. Nenhum valor faturado
(créditos do Free Plan). State do Terraform **local** — nada persistido na conta.

<p align="center">
  <a href="https://github.com/Yuri-Fernando/AWS-Project/blob/main/docs/evidence/aws/aws-inventory.png"><img src="https://raw.githubusercontent.com/Yuri-Fernando/AWS-Project/main/docs/evidence/aws/aws-inventory.png" width="560"></a><br>
  <sub>Inventário lido da conta real durante a sessão: Lambda <code>credit-score-lab-predict</code> ativa, tabela DynamoDB, budgets e o e2e 13/13 (inclui a Lambda e o DynamoDB)</sub>
</p>

Relato completo da sessão (linha do tempo, custo por serviço, desmonte verificado nas 17 regiões):
[AWS-Project/docs/AWS_REAL_SESSION.md](https://github.com/Yuri-Fernando/AWS-Project/blob/main/docs/AWS_REAL_SESSION.md).

Reproduzir: copiar `infra/terraform/lab.tfvars.example` para `lab.tfvars` (gitignored), preencher o e-mail do budget e
rodar `terraform -chdir=infra/terraform apply -var-file=lab.tfvars`; ao terminar, esvaziar o bucket de artefatos e
`terraform destroy -var-file=lab.tfvars`.

---

## 🚀 Aplicações

- Portfólio de ML aplicado a risco de crédito com arquitetura serverless real;
- Referência de MLOps financeiro local-first (contrato, registry, drift, shadow/canary) para quem quer prototipar sem custo de nuvem;
- Material de estudo sobre orquestração via Step Functions/ASL e guard-rails de custo em Terraform.

---

## 🔭 Visão de Longo Prazo

```text
v1 (real, em produção)
├── Lambda · API Gateway · SageMaker · DynamoDB · S3 · Streamlit
        ↓
v2 (local) — Robustez adversarial
        ↓
v3 (local-first) — Contrato, Registry, Handler endurecido, Drift, Shadow/Canary, IaC validado
        ↓
v3.1 (local-first) — Step Functions real, CloudWatch, Guard-rails de custo
        ↓
Pendente por orçamento — apply real, SageMaker Model Registry real, canary com tráfego real,
CloudWatch/X-Ray em produção, WAF, Secrets Manager
```

---

## 🗺️ Roadmap

- **F0 — Fluxo serverless v1** ✅ Concluída — Lambda/API Gateway/SageMaker/DynamoDB/S3/Streamlit, real na AWS.
- **F1 — Robustez adversarial (v2)** ✅ Concluída — evasão, curvas de robustez, adversarial training, model extraction, 6 testes.
- **F2 — MLOps financeiro local-first (v3)** ✅ Concluída — contrato, registry, handler, monitoring, shadow/canary, IaC validado (não aplicado), 14 testes.
- **F3 — Orquestração e guard-rails de custo (v3.1)** ✅ Concluída — Step Functions (ASL real), CloudWatch, `aws_budgets_budget`, `terraform_guard.sh`, 13 testes.
- **F4 — Apply real** 🟡 Parcial — stack serverless v3 aplicada, testada e destruída na AWS real (v3.3.0); SageMaker Model Registry real e canary com tráfego real seguem pendentes por custo.

Detalhes completos: [ROADMAP.md](ROADMAP.md).

---

## 🕓 Histórico e Mudanças

| Versão | Data | O que mudou |
|---|---|---|
| 3.3.0 | 2026-11-11 | `infra/terraform` aplicado na AWS real (Free Plan): key policy do KMS para o CloudWatch Logs, `lambda_reserved_concurrency` e `kms_deletion_window_days` variáveis; Lambda v3 HTTP 200 + DynamoDB; destroy completo |
| 3.2.0 | 2026-10-21 | Governança de ciclo de vida no registry local: `model_owner`/`business_owner`/`risk_tier`/`approval_date`/`review_due_date`, estágios Validation→…→Retirement com transições validadas, revisão vencida bloqueia promoção/deploy, Retirement preserva histórico, `risk_tier` lido do RiskCredit v3.1; 40 testes novos |
| 3.1.0 | 2026-10-07 | Orquestração via Step Functions (ASL real + interpretador local), CloudWatch dashboard/alarmes, guard-rails de custo (AWS Budgets, tags obrigatórias, `terraform_guard.sh`), 13 testes novos |
| 3.0.0 | 2026-09-28 | MLOps financeiro local-first: contrato de dados, registry com aprovação manual, handler endurecido, monitoramento de drift, shadow/canary, IaC validado, 14 testes |
| 2.0.0 | 2026-09-10 | Robustez adversarial: evasão, curvas de robustez, adversarial training, model extraction, 6 testes |
| 1.0.0 | 2025-08-13 | Lambda + API Gateway + SageMaker (XGBoost) + DynamoDB + S3 + Streamlit |

Changelog completo: [CHANGELOG.md](CHANGELOG.md).

---

## 🔮 Próximos Passos

**Concluído nesta versão (3.3.0):**
- ✅ Primeiro `apply` real do IaC v3 (lab Free Plan), com os 3 achados corrigidos e `destroy` completo.

**Concluído na versão 3.2.0:**
- ✅ Governança de ciclo de vida no registry local (responsáveis, `risk_tier`, revisão com vencimento, Retirement com histórico preservado);
- ✅ `risk_tier` lido do `risk_assessment.json` do RiskCredit v3.1, com conferência da versão do modelo e SHA-256 da origem.

**Concluído na versão 3.1.0:**
- ✅ Step Functions real (ASL) + interpretador local equivalente;
- ✅ CloudWatch dashboard/alarmes definidos em IaC;
- ✅ Guard-rails de custo (budget, tags obrigatórias, bloqueio de apply/destroy).

**Dependem de terceiros/orçamento:**
- SageMaker Model Registry real (hoje só a semântica é replicada localmente);
- Canary com tráfego real nas variantes champion/challenger do endpoint;
- WAF (exige REST API ou CloudFront na frente do HTTP API) e Secrets Manager.

**Próximos técnicos (o que eu faria numa v4):**
- Resolver a limitação de drift documentada (PSI do score sempre vermelho em dados sintéticos) com tráfego de produção real antes de confiar no gate;
- Job agendado de drift sobre o DynamoDB real, em vez de rodar só sob demanda;
- Migrar Streamlit da v1 para consumir a API v3 com autenticação Cognito.

---

## ▶️ Como rodar localmente

Pré-requisitos: Python 3.9+ (runtime da Lambda), `pip`, Terraform (para `validate`/`plan` apenas).

```bash
pip install -r requirements.txt
pip install -r requirements-mlops.txt

# Suíte completa (73 testes) — executado nesta revisão
python -m pytest -q tests

# Demo do pipeline de MLOps (registry, handler, drift, shadow/canary) — local, sem AWS
python scripts/mlops_demo.py

# IaC — apenas validação, nunca apply
scripts/terraform_guard.sh validate
cd infra/terraform && terraform validate -var enable_pipeline_orchestration=true
```

Teste local da API v1 / Streamlit (requer endpoint real configurado):

```bash
python teste_api.py
streamlit run App/app.py
```

| Ambiente | Observação |
|---|---|
| Local (sem AWS) | `pytest`, `scripts/mlops_demo.py`, `terraform validate` — tudo o que foi executado nesta revisão |
| Com conta AWS configurada | `teste_api.py`/Streamlit falam com o endpoint v1 real; nada da v2/v3/v3.1 é aplicado automaticamente |
| CI (GitHub Actions) | `.github/workflows/ci.yml` — testes + `terraform fmt/validate` |

`scripts/terraform_guard.sh apply`/`destroy` exigem `TF_GUARD_ALLOW_APPLY=yes-eu-entendo-o-custo` explícito — não foi definido nesta revisão, e nenhum `apply`/`destroy` foi executado.

---

## 📁 Estrutura do repositório

```text
Credit-Score-Predictor---AWS-Streamlit/
├── Nuvem/
│   ├── lambda_function.py         # handler v1, real em produção
│   └── lambda_function_v3.py      # handler v3, não implantado
├── App/
│   └── app.py                     # Streamlit (v1)
├── src/
│   ├── adversarial/                # v2 — evasão, robustez, extração de modelo
│   └── mlops/                      # v3 — contrato, registry, handler, monitoring, shadow, pipeline_steps, asl_runner
├── infra/terraform/                # IaC completo (validate/plan apenas)
│   ├── templates/pipeline.asl.json.tftpl
│   ├── stepfunctions.tf
│   ├── cloudwatch_pipeline.tf
│   └── cost_guardrails.tf
├── scripts/
│   ├── mlops_demo.py
│   └── terraform_guard.sh          # bloqueia apply/destroy sem flag explícita
├── configs/canary_policy.yaml
├── configs/lifecycle_policy.yaml   # v3.2 — intervalos de revisão por tier, origem do risk_assessment.json
├── model_artifacts/riskcredit-v3/  # contrato do champion publicado pelo RiskCredit
├── registry/model_registry.json
├── reports/mlops/
├── tests/                          # 73 testes (6 + 14 + 13 + 40)
├── adversarial_robustness.ipynb
├── requirements.txt / requirements-mlops.txt
├── CHANGELOG.md / ROADMAP.md
└── README.md
```

Não versionado (e por quê): `credenciais aws cli.txt` (segredo local, ignorado pelo `.gitignore`), `node_modules/`, `.terraform/`, `lambda_package.zip`/`lambda_function.zip` (artefatos de build), capturas de tela e rascunhos soltos na raiz (material de sessão, fora do escopo deste README).

---

## 📚 Documentação

| Documento | Conteúdo |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Histórico completo por versão (Keep a Changelog + SemVer) |
| [ROADMAP.md](ROADMAP.md) | Estado item a item do plano, com o que depende de orçamento |

---

## ⚠️ Limitações

- **Nenhum recurso novo das v2/v3/v3.1 foi aplicado na conta AWS** — tudo é `terraform validate`/testes locais, nunca `plan`/`apply` reais;
- O monitoramento de drift do score (PSI) fica "vermelho" para qualquer lote sintético disponível no repositório — é um achado estrutural da amostragem, não um bug de teste (ver Desenvolvimento Experimental);
- O endpoint SageMaker da v1 não deve ser considerado protegido para produção sem mecanismos adicionais de autenticação (Cognito/JWT está no IaC, mas não aplicado);
- O modelo e os resultados dependem dos dados utilizados em seu treinamento; o projeto não constitui uma solução completa de crédito para decisões financeiras reais;
- Não há arquivo de licença (`LICENSE`) na raiz deste repositório nesta revisão — ver seção Licença;
- A governança de ciclo de vida (v3.2) vive só no registry **local**; o SageMaker Model Registry real não foi tocado. O `approver`/`actor` é texto livre — não há autenticação nem assinatura —, a data de vencimento depende do relógio de quem executa e o `risk_tier` é tão confiável quanto a avaliação de origem;
- Esta revisão (v3.2) rodou a suíte completa de testes (72 passed + 1 teste dependente da pasta do RiskCredit, rodado à parte: passou). O `terraform validate` é o da v3.1.0 e **não foi repetido** agora (a v3.2 não altera o IaC); não foi executado `terraform plan`/`apply` nem testes de carga contra o endpoint real.

---

## Status

🟢 **v1 concluída (real na AWS, 2025).** 🟢 **v2/v3/v3.1/v3.2 concluídas localmente** — 73 testes. 🟢 **v3.3.0: IaC serverless v3 aplicado, testado e destruído numa conta AWS real (Free Plan) em 11/11/2026.** Endpoint SageMaker, Step Functions e canary com tráfego real seguem pendentes por custo (ROADMAP).

---

## Contexto / Observações

Projeto de portfólio pessoal, não afiliado a nenhuma empresa ou cliente. A v1 é um deploy real do autor em sua própria conta AWS pessoal, sem usuários externos, tráfego de produção de terceiros ou SLA comercial. Os números de v2/v3/v3.1/v3.2 (testes, paridade, PSI, concordância shadow) são medições reais de execução local, não estimativas de ferramenta nem projeções — e não substituem uma avaliação de risco de crédito real.

---

## 🔗 Projetos Relacionados

| Projeto | Relação |
|---|---|
| [RiskCredit](https://github.com/Yuri-Fernando/RiskCredit) | Publica o modelo champion (XGBoost) consumido como contrato versionado em `model_artifacts/riskcredit-v3/`; a v3.1 gera o `risk_assessment.json` de onde o registry lê o `risk_tier` |
| [AegisLLM](https://github.com/Yuri-Fernando/AegisLLM) | Mesma abordagem de governança (inventário, classificação de risco, aprovação vinculada a hash), aplicada a sistemas de IA generativa |

---

## 🤖 Autor

**Yuri Fernando Dubbern**

Engenharia Elétrica · Ciência da Computação · Inteligência Artificial ·
Sistemas Embarcados · Projeto de Hardware · Pesquisa e Desenvolvimento

[LinkedIn](https://www.linkedin.com/in/yuridubbern) · [GitHub](https://github.com/Yuri-Fernando) · [Lattes](http://lattes.cnpq.br/7151392692642166) · [Linktree](https://linktr.ee/yuri.f.dubbern)

## Licença

Este repositório não possui um arquivo `LICENSE` na raiz nesta revisão. Até que um seja adicionado, considere o código como "todos os direitos reservados" ao autor; para reuso, consulte diretamente o [GitHub do projeto](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit).
