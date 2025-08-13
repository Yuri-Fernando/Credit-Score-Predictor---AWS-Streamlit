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
