"""Dataset UCI "Default of Credit Card Clients" (23 features) para o estudo
de robustez adversarial.

Usa `UCI_Credit_Card.csv` se estiver presente na raiz do projeto; senão,
sintetiza um dataset com o MESMO schema e uma regra de rótulo plausível
(inadimplência sobe com atraso de pagamento e uso alto do limite). Assim o
módulo é testável sem depender do download do dataset.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FEATURES = [
    "LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE",
    "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",
    "BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6",
    "PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6",
]
TARGET = "default.payment.next.month"

_CSV_CANDIDATES = ["UCI_Credit_Card.csv", "../UCI_Credit_Card.csv", "data/UCI_Credit_Card.csv"]


def _synthesize(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "LIMIT_BAL": rng.integers(10_000, 500_000, n).astype(float),
        "SEX": rng.integers(1, 3, n),
        "EDUCATION": rng.integers(1, 5, n),
        "MARRIAGE": rng.integers(1, 4, n),
        "AGE": rng.integers(21, 70, n),
    })
    for c in ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]:
        df[c] = rng.integers(-2, 4, n)
    for c in ["BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6"]:
        df[c] = (rng.random(n) * df["LIMIT_BAL"]).round(0)
    for c in ["PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6"]:
        df[c] = (rng.random(n) * df["LIMIT_BAL"] * 0.1).round(0)

    util = df["BILL_AMT1"] / (df["LIMIT_BAL"] + 1)
    pay_delay = df[["PAY_0", "PAY_2", "PAY_3"]].clip(lower=0).sum(axis=1)
    logit = -2.0 + 1.6 * util + 0.5 * pay_delay - 0.000003 * df["PAY_AMT1"]
    prob = 1 / (1 + np.exp(-logit))
    df[TARGET] = (rng.random(n) < prob).astype(int)
    return df


def load_dataset(n_synth: int = 4000, seed: int = 42) -> pd.DataFrame:
    for cand in _CSV_CANDIDATES:
        p = Path(cand)
        if p.exists():
            df = pd.read_csv(p)
            # o CSV oficial usa "PAY_0"; algumas cópias renomeiam para "PAY_1"
            if "PAY_1" in df.columns and "PAY_0" not in df.columns:
                df = df.rename(columns={"PAY_1": "PAY_0"})
            return df
    return _synthesize(n_synth, seed)


def split(df: pd.DataFrame, test_frac: float = 0.3, seed: int = 42):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(df))
    cut = int(len(df) * (1 - test_frac))
    tr, te = df.iloc[idx[:cut]], df.iloc[idx[cut:]]
    return (
        tr[FEATURES].to_numpy(float), tr[TARGET].to_numpy(int),
        te[FEATURES].to_numpy(float), te[TARGET].to_numpy(int),
    )
