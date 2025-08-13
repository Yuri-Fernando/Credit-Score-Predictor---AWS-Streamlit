# Credit-Score-Predictor---AWS-Streamlit
## Visão Geral
Projeto que integra:
- **AWS Lambda** para predição de crédito via modelo XGBoost hospedado no **SageMaker**.
- **API Gateway** para expor a Lambda.
- **DynamoDB** para armazenar logs e requisições.
- **S3** para armazenar features do modelo.
- **Streamlit** como front-end interativo.

---

## Estrutura do Projeto
- `lambda_function.py` → código da Lambda
- `lambda_package/` → zip com dependências (joblib, boto3, etc)
- `streamlit_app.py` → interface do usuário
- `teste_api.py` → script para teste da Lambda
- `requirements.txt` → dependências do front-end

---

## Configuração AWS

### Lambda
1. Criar Lambda Python 3.9+.
2. Fazer upload do zip em `lambda_package/`.
3. Definir variáveis de ambiente:
   - `MODEL_VERSION=v1`
4. Permissões:
   - Acesso a S3 (read features)
   - Acesso a DynamoDB (write)
   - Acesso a SageMaker (invoke endpoint)

### API Gateway
1. Criar API HTTP.
2. Criar rota `POST /predict` integrando a Lambda.
3. Habilitar endpoint público.
4. Configurar payload como `application/json`.

---

## Testes Locais

### Teste da Lambda
```bash
python teste_api.py

Exemplo de resposta:

{
  "request_id": "54ae0f89-0cf2-49b4-bdda-aad97e21c3c9",
  "score": 0.5699,
  "model_version": "v1",
  "label": null
}

Teste do Streamlit

pip install -r requirements.txt
streamlit run streamlit_app.py

    Preencha os campos de idade, renda e empréstimo.

    Clique em Prever para obter score de crédito.

Payload Esperado

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

Considerações Finais

    Já está funcionando: Lambda + API + Streamlit.

    Próximos passos:

        Testes de edge cases

        Revisão de permissões e segurança

        Logs, tracing e alarmes

        Deploy contínuo (opcional)

Dependências

boto3
joblib
requests
streamlit
