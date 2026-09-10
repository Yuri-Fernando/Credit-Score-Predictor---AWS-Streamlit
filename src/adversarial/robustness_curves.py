"""Curvas de robustez — fração de solicitantes classificados como
`high_risk` cuja decisão pode ser revertida com custo de perturbação até um
orçamento B, para uma faixa de B.

Uma curva que sobe rápido (muitos casos revertíveis com pouco esforço)
indica uma fronteira de decisão frágil / manipulável.
"""
from __future__ import annotations

import numpy as np

from src.adversarial.evasion import minimal_evasion
from src.adversarial.model import CreditRiskModel


def flip_costs(
    model: CreditRiskModel,
    X: np.ndarray,
    max_samples: int = 60,
    n_restarts: int = 3,
    n_steps: int = 20,
    seed: int = 0,
) -> np.ndarray:
    """Custo mínimo de reversão para cada solicitante high_risk (inf se não
    revertível dentro da busca)."""
    X = np.asarray(X, float)
    high_risk = X[model.predict(X) == 1][:max_samples]
    costs = []
    for i, x0 in enumerate(high_risk):
        res = minimal_evasion(model, x0, n_restarts=n_restarts, n_steps=n_steps, seed=seed + i)
        costs.append(res["cost"])
    return np.array(costs, dtype=float)


def robustness_curve(costs: np.ndarray, budgets: list[float] | None = None) -> list[dict]:
    budgets = budgets or [0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
    return [
        {"budget": b, "flippable_fraction": round(float(np.mean(costs <= b)), 4)}
        for b in budgets
    ]
