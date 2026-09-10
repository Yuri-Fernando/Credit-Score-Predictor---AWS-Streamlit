"""Evasion attack tabular — busca a menor perturbação nas features
manipuláveis (sob `feature_constraints`) que faz o modelo mudar a decisão de
`high_risk` para `low_risk`.

Método (real, black-box): busca por coordenada com múltiplos reinícios
aleatórios. Não usa gradiente — só consultas ao `model.score`, exatamente o
que um solicitante externo teria.
"""
from __future__ import annotations

import numpy as np

from src.adversarial.feature_constraints import bounds_for, manipulable_indices
from src.adversarial.model import CreditRiskModel


def _perturbation_cost(x0: np.ndarray, x: np.ndarray) -> float:
    """Custo L1 normalizado da perturbação (só nas features manipuláveis)."""
    idx = manipulable_indices()
    return float(np.sum(np.abs(x[idx] - x0[idx]) / (np.abs(x0[idx]) + 1.0)))


def minimal_evasion(
    model: CreditRiskModel,
    x0: np.ndarray,
    n_restarts: int = 5,
    n_steps: int = 25,
    seed: int = 0,
) -> dict:
    x0 = np.asarray(x0, float)
    idx = manipulable_indices()
    lo, hi = bounds_for(x0)
    rng = np.random.default_rng(seed)

    if model.decision(x0) == "low_risk":
        return {"success": True, "already_low_risk": True, "cost": 0.0, "x_adv": x0.copy()}

    best = None
    for r in range(n_restarts):
        x = x0.copy()
        # perturbação inicial aleatória dentro dos limites
        for j in idx:
            x[j] = rng.uniform(lo[j], hi[j])

        for _ in range(n_steps):
            improved = False
            for j in idx:
                cur = x[j]
                for cand in (lo[j], hi[j], (lo[j] + hi[j]) / 2, x0[j]):
                    x[j] = cand
                    s = model.score(x)[0]
                    if s < model.threshold:
                        cost = _perturbation_cost(x0, x)
                        if best is None or cost < best["cost"]:
                            best = {"success": True, "cost": cost, "x_adv": x.copy(),
                                    "final_score": float(s), "restart": r}
                        improved = True
                x[j] = cur
            if not improved:
                break

    if best is None:
        return {"success": False, "cost": float("inf"), "x_adv": x0.copy()}
    return best
