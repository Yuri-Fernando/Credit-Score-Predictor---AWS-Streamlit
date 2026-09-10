# Credit Score Predictor — AWS + Streamlit

### Machine Learning · AWS Lambda · SageMaker · API Gateway · DynamoDB · S3 · Streamlit

## Status

🟢 **Concluído — Projeto de portfólio / Machine Learning em Cloud**

Aplicação de **predição de risco de crédito** estruturada em uma arquitetura serverless na AWS, integrando **AWS Lambda, API Gateway, SageMaker, DynamoDB, S3 e Streamlit**.

O projeto demonstra o fluxo completo entre uma interface de usuário, uma API serverless, um modelo de Machine Learning hospedado na AWS e camadas de persistência para dados e logs.

---

# Sobre o Projeto

O sistema recebe dados de um cliente, encaminha a requisição para uma função AWS Lambda e utiliza um modelo **XGBoost hospedado no SageMaker** para realizar a inferência.

O resultado retorna para a aplicação e também pode ser registrado no DynamoDB.

```text
Streamlit
    ↓
API Gateway
    ↓
AWS Lambda
    ↓
SageMaker Endpoint
    ↓
XGBoost
    ↓
Prediction / Score
    ↓
DynamoDB
```

O **S3** também participa da arquitetura como camada de armazenamento relacionada às features utilizadas pelo modelo.

---

# Objetivo

Demonstrar a implementação de um pipeline de Machine Learning integrado a serviços AWS, contemplando:

- Inferência de modelo via SageMaker;
- Backend serverless com Lambda;
- Exposição da inferência por API Gateway;
- Persistência de requisições e logs;
- Armazenamento de dados no S3;
- Interface de usuário com Streamlit;
- Integração entre Machine Learning e Cloud Computing.

---

# Arquitetura

```text
                    ┌──────────────────┐
                    │    Streamlit     │
                    │  User Interface  │
                    └────────┬─────────┘
                             │
                             │ POST /predict
                             ▼
                    ┌──────────────────┐
                    │   API Gateway    │
                    │   HTTP API       │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   AWS Lambda     │
                    │ Prediction Logic │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │ SageMaker  │ │ DynamoDB   │ │     S3     │
        │  XGBoost   │ │ Logs/Data  │ │  Features  │
        └────────────┘ └────────────┘ └────────────┘
                │
                ▼
         Credit Score
                │
                ▼
            Streamlit
```

---

# Componentes da Arquitetura

## AWS Lambda

Responsável por:

- Receber a requisição;
- Preparar os dados;
- Consultar o modelo;
- Processar a resposta;
- Registrar informações da execução.

A Lambda funciona como a camada serverless de processamento da aplicação.

---

## API Gateway

Responsável por expor a função Lambda por meio de uma API HTTP.

Rota principal:

```text
POST /predict
```

Payload:

```text
application/json
```

---

## SageMaker

O SageMaker hospeda o modelo de Machine Learning utilizado para gerar o score de crédito.

Modelo:

```text
XGBoost
```

A Lambda realiza a chamada ao endpoint de inferência para obter a previsão.

---

## DynamoDB

Utilizado para registrar informações relacionadas às requisições e resultados.

Exemplo de dados registrados:

- `request_id`;
- Score;
- Versão do modelo;
- Dados relacionados à execução.

---

## S3

Utilizado como camada de armazenamento para features relacionadas ao modelo.

---

## Streamlit

Interface web utilizada para interação com o sistema.

A interface permite informar dados de um cliente e solicitar uma previsão.

---

# Fluxo de Predição

```text
1. Usuário informa os dados
        ↓
2. Streamlit cria o payload
        ↓
3. API Gateway recebe POST /predict
        ↓
4. Lambda processa a requisição
        ↓
5. Lambda consulta SageMaker
        ↓
6. XGBoost realiza a inferência
        ↓
7. Lambda recebe o score
        ↓
8. Resultado é registrado no DynamoDB
        ↓
9. API retorna a resposta
        ↓
10. Streamlit apresenta o resultado
```

---

# Funcionalidades

- Predição de risco de crédito;
- Inferência via SageMaker;
- Backend serverless;
- API HTTP;
- Registro de requisições;
- Versionamento do modelo;
- Interface web interativa;
- Integração com S3;
- Integração com DynamoDB;
- Integração com SageMaker;
- Teste da API via Python.

---

# Exemplo de Resposta

```json
{
  "request_id": "54ae0f89-0cf2-49b4-bdda-aad97e21c3c9",
  "score": 0.5699,
  "model_version": "v1",
  "label": null
}
```

---

# Payload de Entrada

A API espera uma estrutura semelhante a:

```json
{
  "data": {
    "LIMIT_BAL": 50000,
    "SEX": 2,
    "EDUCATION": 2,
    "MARRIAGE": 1,
    "AGE": 30,
    "PAY_0": 0,
    "PAY_2": 0,
    "PAY_3": 0,
    "PAY_4": 0,
    "PAY_5": 0,
    "PAY_6": 0,
    "BILL_AMT1": 3000,
    "BILL_AMT2": 0,
    "BILL_AMT3": 0,
    "BILL_AMT4": 0,
    "BILL_AMT5": 0,
    "BILL_AMT6": 0,
    "PAY_AMT1": 1000,
    "PAY_AMT2": 0,
    "PAY_AMT3": 0,
    "PAY_AMT4": 0,
    "PAY_AMT5": 0,
    "PAY_AMT6": 0
  }
}
```

---

# Estrutura do Projeto

```text
Credit-Score-Predictor---AWS-Streamlit/
│
├── lambda_function.py
│
├── lambda_package/
│   └── ...
│
├── streamlit_app.py
│
├── teste_api.py
│
├── requirements.txt
│
└── README.md
```

---

# Componentes

## `lambda_function.py`

Contém a lógica principal da AWS Lambda, incluindo a comunicação com os serviços utilizados na inferência.

## `lambda_package/`

Pacote utilizado para disponibilizar as dependências necessárias à execução da Lambda.

Entre as dependências estão:

- `joblib`;
- `boto3`;
- outras bibliotecas necessárias ao runtime.

## `streamlit_app.py`

Interface web para entrada dos dados e visualização do resultado.

## `teste_api.py`

Script utilizado para testar a API e validar a comunicação com a Lambda.

## `requirements.txt`

Dependências necessárias para executar a interface e os testes.

---

# Configuração AWS

## Lambda

Criar uma função Lambda com Python 3.9 ou superior.

Configurar:

```text
MODEL_VERSION=v1
```

### Permissões

A Lambda precisa de permissões compatíveis com:

- Leitura no S3;
- Escrita no DynamoDB;
- Invocação do endpoint SageMaker.

---

## API Gateway

Criar uma API HTTP com:

```text
POST /predict
```

Integrada à Lambda.

Payload:

```text
application/json
```

---

# Testes Locais

## Teste da API / Lambda

Execute:

```bash
python teste_api.py
```

O script realiza a chamada e retorna uma estrutura semelhante a:

```json
{
  "request_id": "54ae0f89-0cf2-49b4-bdda-aad97e21c3c9",
  "score": 0.5699,
  "model_version": "v1",
  "label": null
}
```

---

# Teste do Streamlit

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
streamlit run streamlit_app.py
```

A interface permite:

- Informar idade;
- Informar renda;
- Informar valores relacionados ao crédito;
- Enviar os dados;
- Obter o score retornado pela API.

---

# Tecnologias

| Categoria | Tecnologias |
|---|---|
| Linguagem | Python |
| Machine Learning | XGBoost |
| Model Serving | AWS SageMaker |
| Backend | AWS Lambda |
| API | API Gateway |
| Banco / Logs | DynamoDB |
| Storage | Amazon S3 |
| Front-end | Streamlit |
| AWS SDK | boto3 |
| Serialização | joblib |
| Testes | Python / requests |

---

# Casos de Uso

### Credit Risk

Aplicação de Machine Learning à análise de risco de crédito.

### Serverless ML

Execução de inferência sem necessidade de manter um servidor backend dedicado.

### Model Serving

Exposição de modelos treinados por meio de endpoints do SageMaker.

### Cloud-Native ML

Integração entre Machine Learning e diferentes serviços gerenciados da AWS.

### Prototipação de Produtos de IA

Base para aplicações que precisam levar um modelo preditivo até uma interface de usuário.

---

# O que este projeto demonstra

- Machine Learning aplicado a risco de crédito;
- XGBoost;
- Model Serving com SageMaker;
- AWS Lambda;
- API Gateway;
- DynamoDB;
- S3;
- Streamlit;
- Arquitetura serverless;
- Integração entre serviços AWS;
- APIs REST;
- Persistência de requisições;
- Versionamento de modelo;
- Deploy de modelos de Machine Learning;
- Desenvolvimento de aplicações orientadas a dados.

---

# Segurança e Configuração

As credenciais e permissões da AWS devem ser configuradas de acordo com o ambiente utilizado.

Recomendações:

- Não versionar chaves AWS;
- Utilizar IAM com princípio do menor privilégio;
- Manter secrets fora do código;
- Restringir permissões da Lambda;
- Proteger o endpoint quando utilizado fora de ambiente local.

---

# Limitações

- O projeto depende dos serviços AWS configurados;
- O endpoint do SageMaker precisa estar disponível para realizar inferências;
- A arquitetura apresentada é orientada à demonstração e prototipação;
- O endpoint da API não deve ser considerado público ou seguro para produção sem mecanismos adicionais de autenticação e proteção;
- O modelo e os resultados dependem dos dados utilizados em seu treinamento;
- O projeto não constitui uma solução completa de crédito para decisões financeiras reais.

---

# Melhorias Futuras

- Testes de edge cases;
- Autenticação da API;
- Revisão das permissões IAM;
- Logs centralizados;
- Distributed tracing;
- CloudWatch;
- Alarmes;
- Monitoramento de latência;
- Monitoramento de qualidade do modelo;
- CI/CD;
- Infrastructure as Code;
- Versionamento completo do modelo;
- Model Registry;
- Canary deployment;
- API Gateway com autenticação;
- Dashboard operacional;
- Monitoramento de drift.

---

# Próximos Passos

```text
v1
├── Lambda
├── API Gateway
├── SageMaker
├── DynamoDB
├── S3
└── Streamlit

        ↓

Evolução
├── Segurança
├── Observabilidade
├── Monitoramento
├── CI/CD
├── Model Governance
└── Deployment automatizado
```

---

# Status Final

🟢 **Concluído**

A versão atual possui o fluxo principal implementado:

- ✅ AWS Lambda;
- ✅ API Gateway;
- ✅ SageMaker;
- ✅ XGBoost;
- ✅ DynamoDB;
- ✅ S3;
- ✅ Streamlit;
- ✅ API de predição;
- ✅ Registro de requisições;
- ✅ Versionamento do modelo;
- ✅ Teste da API;
- ✅ Interface de predição.

O projeto demonstra a integração entre **Machine Learning, arquitetura serverless e serviços AWS**, levando um modelo preditivo desde a inferência em cloud até uma interface utilizável.

---

# Versão 2.0 — Adversarial Robustness & Model Security

Um modelo financeiro não é só *treinar → accuracy → deploy*. É
*treinar → validar → atacar → medir robustez → mitigar → monitorar*. A V2
adiciona essa camada (`src/adversarial/`), tratando o modelo de risco de
crédito como alvo de ataque.

O modelo de produção é o XGBoost no SageMaker; aqui usamos um **proxy local**
(`HistGradientBoostingClassifier` sobre o mesmo schema UCI de 23 features)
para estudar robustez sem depender do endpoint.

## O que foi adicionado

- `src/adversarial/dataset.py` — carrega `UCI_Credit_Card.csv` se presente;
  senão sintetiza o mesmo schema (23 features) com regra de rótulo plausível.
- `src/adversarial/feature_constraints.py` — **quais features um solicitante
  consegue manipular** (`PAY_AMT*`, `BILL_AMT*` recentes, com limites) vs.
  imutáveis (`SEX`, `AGE`, `EDUCATION`, `MARRIAGE`, `LIMIT_BAL`, histórico
  `PAY_*`). Sem isso, "ataque tabular" viraria trocar idade ou sexo.
- `src/adversarial/evasion.py` — **evasão de perturbação mínima** (busca por
  coordenada black-box, só consultas ao score): menor mudança nas features
  manipuláveis que reverte `high_risk → low_risk`.
- `src/adversarial/robustness_curves.py` — fração de decisões `high_risk`
  revertíveis por orçamento de perturbação B.
- `src/adversarial/adversarial_training.py` — retreino com exemplos evadidos
  (ainda rotulados como alto risco) para endurecer a fronteira.
- `src/adversarial/model_extraction.py` — substituto treinado só com as
  decisões do modelo-alvo (`fidelity`).
- `adversarial_robustness.ipynb` — walkthrough completo.
- 6 testes (`tests/test_adversarial.py`, dataset sintético, determinísticos).

## Cenário

```text
cliente real         renda ↑ levemente, pagamento ↑ levemente (dentro do plausível)
score 0.62  ──────▶  score 0.48
high_risk            low_risk        ← fronteira revertível com pouca perturbação
```

O módulo mede o **orçamento mínimo de perturbação** necessário para mudar a
decisão — e o `adversarial_training` aumenta esse orçamento.

## Integração com o portfólio

Caso de uso de **adversarial tabular** da trilha de AI Security centralizada
no **ThemisAI** (`core/adversarial_ml/`). O `ModelSecurityReport` gerado
alimenta o *robustness gate* do **Argus** (`ml-platform/adversarial-evaluation/`).
Ver também VisionGuard (adversarial vision), RL-PID-AGV (adversarial RL) e
Churn (robustness testing).

---

# Autor

**Yuri Fernando Dubbern**

AI/ML Engineer · Machine Learning · AWS · Data Engineering · Cloud AI

[LinkedIn](https://www.linkedin.com/in/yuridubbern) · [GitHub](https://github.com/Yuri-Fernando) · [Lattes](http://lattes.cnpq.br/7151392692642166) · [Linktree](https://linktr.ee/yuri.f.dubbern)
