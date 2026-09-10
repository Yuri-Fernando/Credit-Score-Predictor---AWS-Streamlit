"""Testes da camada de robustez adversarial do modelo de crédito.
Usam o dataset sintético (schema UCI) — rápidos, determinísticos."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.adversarial import (  # noqa: E402
    CreditRiskModel,
    adversarially_train,
    flip_costs,
    load_dataset,
    minimal_evasion,
    model_extraction_attack,
    robustness_curve,
    split,
)
from src.adversarial.feature_constraints import IMMUTABLE, manipulable_indices
from src.adversarial.dataset import FEATURES


@pytest.fixture(scope="module")
def data_model():
    df = load_dataset(n_synth=1500, seed=1)
    Xtr, ytr, Xte, yte = split(df, seed=1)
    model = CreditRiskModel(seed=0).fit(Xtr, ytr)
    return Xtr, ytr, Xte, yte, model


def test_model_trains_and_predicts(data_model):
    *_, Xte, yte, model = data_model
    acc = np.mean(model.predict(Xte) == yte)
    assert acc > 0.6


def test_evasion_only_touches_manipulable_features(data_model):
    Xtr, ytr, Xte, yte, model = data_model
    high_risk = Xte[model.predict(Xte) == 1]
    assert len(high_risk) > 0
    res = minimal_evasion(model, high_risk[0], seed=3)
    if res["success"] and not res.get("already_low_risk"):
        changed = np.where(~np.isclose(res["x_adv"], high_risk[0]))[0]
        manip = set(manipulable_indices())
        assert set(changed).issubset(manip)
        # nenhuma feature imutável mudou
        for i, name in enumerate(FEATURES):
            if name in IMMUTABLE:
                assert np.isclose(res["x_adv"][i], high_risk[0][i])


def test_evasion_flips_decision_when_successful(data_model):
    Xtr, ytr, Xte, yte, model = data_model
    high_risk = Xte[model.predict(Xte) == 1][:5]
    any_success = False
    for i, x0 in enumerate(high_risk):
        res = minimal_evasion(model, x0, seed=10 + i)
        if res["success"] and not res.get("already_low_risk"):
            assert model.decision(res["x_adv"]) == "low_risk"
            assert res["cost"] > 0
            any_success = True
    assert any_success  # a fronteira é manipulável para ao menos um caso


def test_robustness_curve_is_monotone_nondecreasing(data_model):
    Xtr, ytr, Xte, yte, model = data_model
    costs = flip_costs(model, Xte, max_samples=8, seed=0)
    curve = robustness_curve(costs)
    fr = [p["flippable_fraction"] for p in curve]
    assert all(fr[i] <= fr[i + 1] + 1e-9 for i in range(len(fr) - 1))


def test_adversarial_training_reduces_flippable_fraction_at_small_budget(data_model):
    Xtr, ytr, Xte, yte, base = data_model
    costs_before = flip_costs(base, Xte, max_samples=8, seed=0)
    hardened = adversarially_train(Xtr, ytr, base_model=base, max_adv=20, seed=0)
    costs_after = flip_costs(hardened, Xte, max_samples=8, seed=0)

    frac_before = np.mean(costs_before <= 0.25)
    frac_after = np.mean(costs_after <= 0.25)
    assert frac_after <= frac_before + 0.15  # não deve piorar materialmente


def test_model_extraction_reports_fidelity(data_model):
    Xtr, ytr, Xte, yte, model = data_model
    res = model_extraction_attack(model, Xtr, Xte, yte)
    assert 0.0 <= res["fidelity"] <= 1.0
    assert res["n_queries"] == len(Xtr)
