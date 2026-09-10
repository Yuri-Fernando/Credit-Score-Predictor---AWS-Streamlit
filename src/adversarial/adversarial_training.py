"""Adversarial training tabular — aumenta o conjunto de treino com versões
evadidas de solicitantes high_risk (rotuladas como high_risk mesmo assim) e
retreina. Objetivo: empurrar a fronteira para que a mesma perturbação
pequena não mude mais a decisão.
"""
from __future__ import annotations

import numpy as np

from src.adversarial.evasion import minimal_evasion
from src.adversarial.model import CreditRiskModel


def adversarially_train(
    X_train: np.ndarray,
    y_train: np.ndarray,
    base_model: CreditRiskModel | None = None,
    max_adv: int = 80,
    seed: int = 0,
) -> CreditRiskModel:
    X_train = np.asarray(X_train, float)
    y_train = np.asarray(y_train, int)

    base = base_model or CreditRiskModel(seed=seed).fit(X_train, y_train)

    high_risk = X_train[base.predict(X_train) == 1][:max_adv]
    adv_rows, adv_labels = [], []
    for i, x0 in enumerate(high_risk):
        res = minimal_evasion(base, x0, n_restarts=4, n_steps=25, seed=seed + i)
        if res["success"] and not res.get("already_low_risk"):
            adv_rows.append(res["x_adv"])
            adv_labels.append(1)  # continua sendo um caso de alto risco

    if adv_rows:
        X_aug = np.vstack([X_train, np.array(adv_rows)])
        y_aug = np.concatenate([y_train, np.array(adv_labels)])
    else:
        X_aug, y_aug = X_train, y_train

    return CreditRiskModel(seed=seed).fit(X_aug, y_aug)
