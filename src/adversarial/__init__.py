"""Adversarial Robustness & Model Security — camada de segurança sobre o
modelo de risco de crédito (proxy local do XGBoost/SageMaker).

- evasão tabular com **feature constraints** (só o que o solicitante
  consegue manipular);
- curvas de robustez (fração de decisões revertíveis por orçamento de
  perturbação);
- adversarial training tabular;
- model extraction por consulta.

`train → validate → attack → measure robustness → mitigate → monitor`, em
vez de só `train → accuracy → deploy`.
"""
from __future__ import annotations

from src.adversarial.adversarial_training import adversarially_train
from src.adversarial.dataset import load_dataset, split
from src.adversarial.evasion import minimal_evasion
from src.adversarial.model import CreditRiskModel
from src.adversarial.model_extraction import model_extraction_attack
from src.adversarial.robustness_curves import flip_costs, robustness_curve

__all__ = [
    "load_dataset",
    "split",
    "CreditRiskModel",
    "minimal_evasion",
    "flip_costs",
    "robustness_curve",
    "adversarially_train",
    "model_extraction_attack",
]
