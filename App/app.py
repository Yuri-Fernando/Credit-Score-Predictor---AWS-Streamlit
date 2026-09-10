import streamlit as st
import requests

st.set_page_config(page_title="Credit Score Predictor", layout="centered")
st.title("Credit Score Predictor")
st.write("Preencha os dados abaixo para prever o score de crédito baseado na tabela UCI.")

# =======================
# Inputs principais
# =======================
age = st.number_input("AGE", min_value=18, max_value=100, value=30)
income = st.number_input("BILL_AMT1 (R$)", min_value=0, value=3000)
loan_amount = st.number_input("PAY_AMT1 (R$)", min_value=0, value=1000)

# =======================
# Payload completo com defaults e inputs do usuário
# =======================
payload = {
    "data": {
        "LIMIT_BAL": 50000,
        "SEX": 2,
        "EDUCATION": 2,
        "MARRIAGE": 1,
        "AGE": age,
        "PAY_0": 0,
        "PAY_2": 0,
        "PAY_3": 0,
        "PAY_4": 0,
        "PAY_5": 0,
        "PAY_6": 0,
        "BILL_AMT1": income,
        "BILL_AMT2": 0,
        "BILL_AMT3": 0,
        "BILL_AMT4": 0,
        "BILL_AMT5": 0,
        "BILL_AMT6": 0,
        "PAY_AMT1": loan_amount,
        "PAY_AMT2": 0,
        "PAY_AMT3": 0,
        "PAY_AMT4": 0,
        "PAY_AMT5": 0,
        "PAY_AMT6": 0
    }
}

# =======================
# Botão de previsão
# =======================
if st.button("Prever Score"):
    lambda_url = "https://2jvq4441x4.execute-api.sa-east-1.amazonaws.com/predict"
    try:
        response = requests.post(lambda_url, json=payload)
        response.raise_for_status()
        result = response.json()
        st.success(f"Score previsto: {result.get('score', 'Erro ao obter previsão')}")
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao conectar com a API: {e}")
    except Exception as e:
        st.error(f"Erro ao processar a resposta: {e}")
