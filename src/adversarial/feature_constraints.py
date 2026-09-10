"""Restrições de features — o que um solicitante de crédito consegue, de
fato, manipular numa tentativa de evasão.

Sem isso, um "ataque adversarial tabular" viraria trocar SEX ou AGE, o que
não faz sentido de negócio. O ataque só pode mexer no que é plausivelmente
sob controle do solicitante (valores de pagamento e, em menor grau, faturas
recentes), dentro de limites.
"""
from __future__ import annotations

import numpy as np

from src.adversarial.dataset import FEATURES

# features imutáveis num ataque realista
IMMUTABLE = {
    "SEX", "EDUCATION", "MARRIAGE", "AGE", "LIMIT_BAL",
    "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",  # histórico de atraso já registrado
}

# features manipuláveis e o passo/limite relativo permitido
MANIPULABLE = {
    "PAY_AMT1": 0.5, "PAY_AMT2": 0.5, "PAY_AMT3": 0.3,
    "PAY_AMT4": 0.3, "PAY_AMT5": 0.2, "PAY_AMT6": 0.2,
    "BILL_AMT1": 0.2, "BILL_AMT2": 0.1, "BILL_AMT3": 0.1,
}


def manipulable_indices() -> list[int]:
    return [FEATURES.index(f) for f in FEATURES if f in MANIPULABLE]


def bounds_for(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Dado um vetor de features `x`, retorna (lo, hi) por feature: as
    imutáveis ficam fixas em `x`; as manipuláveis podem variar ± `rel * |x|`
    (mínimo de uma folga absoluta), e nunca abaixo de 0."""
    lo = x.copy().astype(float)
    hi = x.copy().astype(float)
    for f, rel in MANIPULABLE.items():
        i = FEATURES.index(f)
        slack = max(abs(x[i]) * rel, 500.0)
        lo[i] = max(0.0, x[i] - slack)
        hi[i] = x[i] + slack
    return lo, hi
