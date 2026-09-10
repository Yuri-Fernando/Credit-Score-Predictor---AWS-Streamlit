"""Model extraction — treina um substituto do modelo de crédito só com
pares (features, decisão) obtidos por consulta ao endpoint. `fidelity` alta
significa que o modelo pode ser reconstruído por quem só tem acesso à API
(risco de PI e de facilitar ataques de transferência).
"""
from __future__ import annotations

import numpy as np

from src.adversarial.model import CreditRiskModel


def model_extraction_attack(
    target: CreditRiskModel,
    X_query: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    seed: int = 0,
) -> dict:
    X_query = np.asarray(X_query, float)
    X_test = np.asarray(X_test, float)
    y_test = np.asarray(y_test, int)

    y_stolen = target.predict(X_query)
    surrogate = CreditRiskModel(seed=seed).fit(X_query, y_stolen)

    target_pred = target.predict(X_test)
    surr_pred = surrogate.predict(X_test)

    return {
        "n_queries": len(X_query),
        "fidelity": round(float(np.mean(surr_pred == target_pred)), 4),
        "surrogate_accuracy": round(float(np.mean(surr_pred == y_test)), 4),
        "target_accuracy": round(float(np.mean(target_pred == y_test)), 4),
    }
