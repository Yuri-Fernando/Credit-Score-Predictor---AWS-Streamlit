import requests

url = "https://2jvq4441x4.execute-api.sa-east-1.amazonaws.com/predict"

payload = {
    "data": {
        "LIMIT_BAL": 20000,
        "SEX": 2,
        "EDUCATION": 2,
        "MARRIAGE": 1,
        "AGE": 24,
        "PAY_0": 2,
        "PAY_2": 2,
        "PAY_3": -1,
        "PAY_4": -1,
        "BILL_AMT1": 0,
        "BILL_AMT2": 0,
        "BILL_AMT3": 0,
        "BILL_AMT4": 0,
        "BILL_AMT5": 0,
        "BILL_AMT6": 0,
        "PAY_AMT1": 0,
        "PAY_AMT2": 689,
        "PAY_AMT3": 0,
        "PAY_AMT4": 0,
        "PAY_AMT5": 0,
        "PAY_AMT6": 0
    }
}

headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)

print("Status code:", response.status_code)
print("Response:", response.text)
