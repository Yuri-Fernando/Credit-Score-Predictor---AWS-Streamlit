"""Inferência local do champion RiskCredit V3 (XGBoost em JSON nativo).

Mesmo artefato que seria publicado no endpoint SageMaker (container XGBoost);
aqui roda local para testes de contrato, shadow e monitoramento sem custo.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from src.mlops.features import engineer

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "model_artifacts" / "riskcredit-v3"
RISK_BANDS = [(0.05, "A"), (0.10, "B"), (0.20, "C"), (0.35, "D"), (0.60, "E"), (1.01, "F")]


def risk_band(pd_: float) -> str:
    return next(label for cut, label in RISK_BANDS if pd_ < cut)


class LocalScorer:
    def __init__(self, artifact_dir: str | Path = ARTIFACT_DIR):
        d = Path(artifact_dir)
        self.card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
        schema = json.loads((d / "feature_schema.json").read_text(encoding="utf-8"))
        self.features = schema["model_features_ordered"]
        self.booster = xgb.Booster()
        self.booster.load_model(str(d / "xgboost-model.json"))
        self.model_version = self.card["version"]

    def model_frame(self, records: list[dict]) -> pd.DataFrame:
        return engineer(pd.DataFrame(records))[self.features]

    def predict_pd(self, records: list[dict]) -> np.ndarray:
        X = self.model_frame(records)
        return self.booster.predict(xgb.DMatrix(X, feature_names=self.features))
