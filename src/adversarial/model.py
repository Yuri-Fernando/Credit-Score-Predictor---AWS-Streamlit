"""Modelo-alvo local — proxy do XGBoost hospedado no SageMaker.

Treina um `HistGradientBoostingClassifier` (sklearn, sem dependência nativa
de xgboost) sobre o schema UCI. A interface (`predict_proba`, `predict`,
`decision`) é a mesma que o Lambda expõe: entra um vetor de 23 features,
sai um score de inadimplência e uma decisão high/low risk.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

RISK_THRESHOLD = 0.5


class CreditRiskModel:
    def __init__(self, threshold: float = RISK_THRESHOLD, seed: int = 0):
        self.threshold = threshold
        self._clf = HistGradientBoostingClassifier(
            max_depth=6, learning_rate=0.1, max_iter=150, random_state=seed
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CreditRiskModel":
        self._clf.fit(np.asarray(X, float), np.asarray(y, int))
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self._clf.predict_proba(np.atleast_2d(np.asarray(X, float)))

    def score(self, X: np.ndarray) -> np.ndarray:
        """Probabilidade de inadimplência (classe 1)."""
        return self.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.score(X) >= self.threshold).astype(int)

    def decision(self, x: np.ndarray) -> str:
        return "high_risk" if self.score(x)[0] >= self.threshold else "low_risk"
