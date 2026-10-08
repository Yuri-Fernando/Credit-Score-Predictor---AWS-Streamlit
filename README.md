# 💳 Credit Score Predictor — AWS + Streamlit — de inferência serverless a MLOps financeiro orquestrado

### Python · AWS Lambda · SageMaker · API Gateway · DynamoDB · S3 · Step Functions · Terraform · XGBoost · Streamlit

[![ci](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit/actions/workflows/ci.yml/badge.svg)](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit/actions/workflows/ci.yml)
![testes](https://img.shields.io/badge/testes-33%20passed-0a8a0a)
![IaC](https://img.shields.io/badge/IaC-validate%2Fplan%20only-2a78d6)
![versão](https://img.shields.io/badge/vers%C3%A3o-v3.1.0-4a5563) ![license](https://img.shields.io/badge/license-sem%20arquivo-4a5563)

## Status

🟢 **Concluído no escopo v1 (fluxo serverless real) — v3.1.0 adiciona MLOps, orquestração e guard-rails de custo, tudo validado localmente.**

A v1 (Lambda + API Gateway + SageMaker + DynamoDB + S3 + Streamlit) é o fluxo real em produção na conta AWS do autor, implantado em 2025. As v2/v3/v3.1 (robustez adversarial, MLOps financeiro, orquestração via Step Functions, CloudWatch e guard-rails de custo) são **inteiramente locais**: 33 testes passaram nesta revisão, mas **nenhum `terraform apply`/`destroy` foi executado** — toda a infraestrutura nova existe apenas como `terraform validate`/`plan`, nunca aplicada na conta.

| Camada | Estado | Evidência |
|---|---|---|
| v1 — Lambda/API Gateway/SageMaker/DynamoDB/S3/Streamlit | 🟢 Real, implantado na AWS | Fluxo em produção desde 2025 |
| v2 — Robustez adversarial (proxy local) | 🟢 Local, testado | 6 testes (`tests/test_adversarial.py`) |
| v3 — MLOps financeiro (registry, contrato, drift, shadow/canary) | 🟢 Local, testado · IaC validado | 14 testes (`tests/test_mlops.py`) |
| v3.1 — Orquestração (Step Functions), CloudWatch, guard-rails de custo | 🟢 Local, testado · IaC validado | 13 testes (`tests/test_stepfunctions.py`) |

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

---

## 🧠 Verificação / Validação

| Camada | O que prova | Resultado |
|---|---|---|
| `tests/test_adversarial.py` (6) | Evasão de perturbação mínima funciona sobre features manipuláveis reais, não idade/sexo | 6 passed |
| `tests/test_mlops.py` (14) | Contrato rejeita dado inválido; registry aplica gates; handler responde 400/413/422/500 corretamente | 14 passed |
| `tests/test_stepfunctions.py` (13) | ASL real é estruturalmente válido; simulação local ponta-a-ponta reflete o resultado real de drift; os 4 ramos do `Choice` são testados isoladamente | 13 passed |
| Paridade RiskCredit ↔ handler v3 | Mesma engenharia de features que o modelo de origem | máx \|Δ PD\| = 5e-7 nas 25 golden samples |
| `terraform validate` (com e sem `enable_pipeline_orchestration`) | IaC é sintaticamente e estruturalmente válido | Validado nesta revisão, **sem apply/plan contra a conta** |

Execução nesta revisão: `python -m pytest -q tests` → **33 passed** (6 + 14 + 13), confirmado nesta sessão.

---

## 🧪 Desenvolvimento Experimental

**Achado honesto, não um bug de teste:** o monitoramento de drift do score (PSI) fica "vermelho" para **qualquer** lote sintético disponível no repositório — tanto golden samples (casos de borda) quanto amostragem independente por feature do perfil de referência.

- **Hipótese inicial:** um lote amostrado do próprio perfil de treino deveria aparecer como "sem drift" (PSI baixo) no monitoramento.
- **O que se testou:** `src/mlops/monitoring.py` mede PSI por feature e do score; o teste ponta-a-ponta (`tests/test_stepfunctions.py`) roda esse cálculo sobre lotes sintéticos reais do repositório, sem mockar o resultado.
- **Causa real:** a amostragem independente por feature preserva as marginais de cada variável, mas destrói a estrutura conjunta (correlação entre features) que existia no treino real — é exatamente esse tipo de drift estrutural que o PSI por feature não detecta, mas o PSI do score detecta.
- **Decisão de design:** em vez de forçar um "caminho feliz" artificial, o teste ponta-a-ponta reflete esse resultado real — o pipeline suspende a publicação em `HoldForDriftReview`. Os 4 ramos de decisão (rollback / hold-drift / hold-canary / promote) são testados isoladamente a partir do estado `CheckCanaryAndDrift`, para não depender só do caminho que o lote sintético disponível força. A mitigação real (tráfego de produção de verdade em vez de dados sintéticos) fica documentada no ROADMAP.

---

## 🛠️ Tecnologias

- **Linguagem:** Python
- **Machine Learning:** XGBoost, scikit-learn (`HistGradientBoostingClassifier` como proxy local)
- **AWS (v1, real):** Lambda, API Gateway, SageMaker, DynamoDB, S3
- **AWS (v3/v3.1, IaC validado, não aplicado):** Step Functions, CloudWatch, AWS Budgets, KMS, IAM, Cognito/JWT
- **IaC:** Terraform (`terraform fmt/validate/plan` apenas)
- **Front-end:** Streamlit
- **Qualidade:** pytest, CI (GitHub Actions)

---

## 📊 Resultados

| Métrica | Valor | Origem |
|---|---|---|
| Testes totais | 33 passed | `python -m pytest -q tests`, executado nesta sessão |
| Paridade RiskCredit vs handler v3 | máx \|Δ PD\| = 5e-7 | 25 golden samples, `scripts/mlops_demo.py` |
| Registry | Pacote aprovado por gates (Gini ≥ 0,45, ECE ≤ 0,02, PSI < 0,10) | `scripts/mlops_demo.py` |
| Drift — lote estável amostrado do perfil | 28/28 features verdes; score vermelho (PSI 0,67) | `scripts/mlops_demo.py`, ver achado acima |
| Drift — tráfego sintético V2 | 29/29 vermelhos | `scripts/mlops_demo.py` |
| Shadow — challenger V2 | Concordância 86%, PSI de score 0,85, Spearman 0,43 → canary **hold** | `scripts/mlops_demo.py` |
| IaC | `terraform validate` ok nos dois valores de `enable_pipeline_orchestration` | `scripts/terraform_guard.sh validate` |

Nenhum número acima vem de execução real contra a conta AWS para as camadas v2/v3/v3.1 — todos são execuções locais (`pytest`, `scripts/mlops_demo.py`, `terraform validate`).

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
- **F4 — Apply real condicionado a orçamento** ⏸️ Pendente por custo — `terraform plan`/`apply` em conta de staging, SageMaker Model Registry real, canary com tráfego real.

Detalhes completos: [ROADMAP.md](ROADMAP.md).

---

## 🕓 Histórico e Mudanças

| Versão | Data | O que mudou |
|---|---|---|
| 3.1.0 | 2026-10-07 | Orquestração via Step Functions (ASL real + interpretador local), CloudWatch dashboard/alarmes, guard-rails de custo (AWS Budgets, tags obrigatórias, `terraform_guard.sh`), 13 testes novos |
| 3.0.0 | 2026-09-28 | MLOps financeiro local-first: contrato de dados, registry com aprovação manual, handler endurecido, monitoramento de drift, shadow/canary, IaC validado, 14 testes |
| 2.0.0 | 2026-09-10 | Robustez adversarial: evasão, curvas de robustez, adversarial training, model extraction, 6 testes |
| 1.0.0 | 2025-08-13 | Lambda + API Gateway + SageMaker (XGBoost) + DynamoDB + S3 + Streamlit |

Changelog completo: [CHANGELOG.md](CHANGELOG.md).

---

## 🔮 Próximos Passos

**Concluído nesta versão (3.1.0):**
- ✅ Step Functions real (ASL) + interpretador local equivalente;
- ✅ CloudWatch dashboard/alarmes definidos em IaC;
- ✅ Guard-rails de custo (budget, tags obrigatórias, bloqueio de apply/destroy).

**Dependem de terceiros/orçamento:**
- `terraform plan`/`apply` real em conta de staging com orçamento aprovado;
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

# Suíte completa (33 testes) — executado nesta revisão
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
├── model_artifacts/riskcredit-v3/  # contrato do champion publicado pelo RiskCredit
├── registry/model_registry.json
├── reports/mlops/
├── tests/                          # 33 testes (6 + 14 + 13)
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
- Esta revisão rodou a suíte completa de testes (33 passed) e `terraform validate`; não foi executado `terraform plan`/`apply` nem testes de carga contra o endpoint real.

---

## Status

🟢 **v1 concluída e real em produção na AWS.** 🟢 **v2/v3/v3.1 concluídas localmente** — 33 testes passando (confirmado nesta revisão), IaC validado para orquestração via Step Functions, CloudWatch e guard-rails de custo. Nenhum `apply`/`destroy` foi executado contra a conta; o que depende de orçamento está documentado no ROADMAP.

---

## Contexto / Observações

Projeto de portfólio pessoal, não afiliado a nenhuma empresa ou cliente. A v1 é um deploy real do autor em sua própria conta AWS pessoal, sem usuários externos, tráfego de produção de terceiros ou SLA comercial. Os números de v2/v3/v3.1 (testes, paridade, PSI, concordância shadow) são medições reais de execução local, não estimativas de ferramenta nem projeções — e não substituem uma avaliação de risco de crédito real.

---

## 🔗 Projetos Relacionados

| Projeto | Relação |
|---|---|
| [RiskCredit](https://github.com/Yuri-Fernando/RiskCredit) | Publica o modelo champion (XGBoost) consumido como contrato versionado em `model_artifacts/riskcredit-v3/` |

---

## 🤖 Autor

**Yuri Fernando Dubbern**

Engenharia Elétrica · Ciência da Computação · Inteligência Artificial ·
Sistemas Embarcados · Projeto de Hardware · Pesquisa e Desenvolvimento

[LinkedIn](https://www.linkedin.com/in/yuridubbern) · [GitHub](https://github.com/Yuri-Fernando) · [Lattes](http://lattes.cnpq.br/7151392692642166) · [Linktree](https://linktr.ee/yuri.f.dubbern)

## Licença

Este repositório não possui um arquivo `LICENSE` na raiz nesta revisão. Até que um seja adicionado, considere o código como "todos os direitos reservados" ao autor; para reuso, consulte diretamente o [GitHub do projeto](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit).
