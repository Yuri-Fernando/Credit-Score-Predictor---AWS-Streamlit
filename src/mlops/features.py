"""Engenharia de atributos do contrato RiskCredit V3.

Cópia fiel de ``src/data/load.py::engineer`` do repositório RiskCredit
(commit em ``model_artifacts/riskcredit-v3/SOURCE_COMMIT``). A paridade é
garantida por teste: ``golden_samples.json`` (entrada bruta → PD esperada)
precisa ser reproduzido aqui com tolerância 1e-6.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PAY = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL = [f"BILL_AMT{i}" for i in range(1, 7)]
PAYAMT = [f"PAY_AMT{i}" for i in range(1, 7)]


def _slope(Y: np.ndarray, x: np.ndarray) -> np.ndarray:
    xc = x - x.mean()
    return ((Y - Y.mean(axis=1, keepdims=True)) * xc).sum(axis=1) / (xc**2).sum()


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    pay = out[PAY].clip(lower=0)
    out["mean_delay"] = pay.mean(axis=1)
    out["max_delay"] = pay.max(axis=1)
    out["n_months_delayed"] = (pay > 0).sum(axis=1)
    lim = out["LIMIT_BAL"].clip(lower=1)
    out["utilization"] = (out["BILL_AMT1"] / lim).clip(-1, 5)
    out["utilization_avg"] = (out[BILL].mean(axis=1) / lim).clip(-1, 5)
    bills = out[BILL].clip(lower=0)
    out["pay_ratio"] = (out["PAY_AMT1"] / bills["BILL_AMT2"].replace(0, np.nan)).fillna(1.0).clip(0, 5)
    out["pay_ratio_avg"] = (out[PAYAMT].sum(axis=1) / bills.sum(axis=1).replace(0, np.nan)).fillna(1.0).clip(0, 5)
    months = np.arange(6)[::-1]
    out["bill_trend"] = _slope(out[BILL].to_numpy(float), months) / lim
    out["pay_trend"] = _slope(out[PAYAMT].to_numpy(float), months) / lim
    return out
