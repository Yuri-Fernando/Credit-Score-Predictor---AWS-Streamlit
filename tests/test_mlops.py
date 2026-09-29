"""Testes do MLOps v3 local: contrato, paridade com o RiskCredit, handler,
registry, monitoramento e shadow/canary. Nenhum teste chama a AWS."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["INFERENCE_MODE"] = "local"
os.environ["PERSIST"] = "false"

from src.mlops import handler  # noqa: E402
from src.mlops.contract import MAX_BATCH, FeatureContract  # noqa: E402
from src.mlops.monitoring import drift_report, operational_metrics, psi_against_reference, sample_from_reference  # noqa: E402
from src.mlops.registry import APPROVED, PENDING, REJECTED, GateFailed, LocalModelRegistry  # noqa: E402
from src.mlops.scoring import ARTIFACT_DIR, LocalScorer, risk_band  # noqa: E402
from src.mlops.shadow import canary_decision  # noqa: E402

GOLDEN = json.loads((ARTIFACT_DIR / "golden_samples.json").read_text(encoding="utf-8"))
CONTRACT = FeatureContract.from_file(ARTIFACT_DIR / "feature_schema.json")


def test_contract_parity_with_riskcredit_golden_samples():
    """Engenharia de atributos + XGBoost local reproduzem a PD publicada pelo RiskCredit."""
    got = LocalScorer().predict_pd([g["input"] for g in GOLDEN])
    np.testing.assert_allclose(got, [g["expected_pd"] for g in GOLDEN], atol=1e-6)


def test_contract_rejects_instead_of_zero_filling():
    rec = dict(GOLDEN[0]["input"])
    rec.pop("PAY_AMT3")
    errs = CONTRACT.validate_record(rec)
    assert errs == [{"record": 0, "field": "PAY_AMT3", "error": "campo_obrigatorio_ausente"}]


@pytest.mark.parametrize("field,value,code", [
    ("PAY_0", 1.5, "status_de_pagamento_deve_ser_inteiro"),
    ("PAY_0", 12, "fora_da_faixa_valida"),
    ("LIMIT_BAL", -10, "fora_da_faixa_valida"),
    ("PAY_AMT1", "100", "tipo_invalido"),
    ("BILL_AMT1", float("nan"), "valor_nao_finito"),
])
def test_contract_field_rules(field, value, code):
    rec = {**GOLDEN[0]["input"], field: value}
    assert any(e["error"] == code and e["field"] == field for e in CONTRACT.validate_record(rec))


def test_contract_blocks_excluded_and_unknown_attributes():
    errs = CONTRACT.validate_record({**GOLDEN[0]["input"], "SEX": 2, "foo": 1})
    codes = {e["field"]: e["error"] for e in errs}
    assert codes == {"SEX": "atributo_excluido_do_modelo", "foo": "campo_nao_permitido"}


def test_handler_status_codes_and_no_value_echo():
    ok = handler.lambda_handler({"body": json.dumps({"data": GOLDEN[0]["input"]})})
    assert ok["statusCode"] == 200
    body = json.loads(ok["body"])
    assert body["results"][0]["risk_band"] == risk_band(body["results"][0]["pd"])
    bad = handler.lambda_handler({"body": json.dumps({"data": {**GOLDEN[0]["input"], "LIMIT_BAL": -999999}})})
    assert bad["statusCode"] == 422 and "-999999" not in bad["body"]
    assert handler.lambda_handler({"body": "{x"})["statusCode"] == 400
    big = handler.lambda_handler({"body": json.dumps({"records": [GOLDEN[0]["input"]] * 400})})
    assert big["statusCode"] == 413
    many = handler.lambda_handler({"body": json.dumps({"records": [GOLDEN[0]["input"]] * (MAX_BATCH + 1)})})
    assert many["statusCode"] in (400, 413)
    assert handler.lambda_handler(GOLDEN[0]["input"] | {})["statusCode"] == 400  # sem envelope data/records


def test_handler_logs_without_input_values():
    handler.LOG_SINK.clear()
    handler.lambda_handler({"body": json.dumps({"data": GOLDEN[1]["input"]})})
    rec = handler.LOG_SINK[-1]
    assert set(rec) == {"event", "request_id", "status_code", "model_version", "n_records", "latency_ms"}
    ops = operational_metrics(handler.LOG_SINK)
    assert ops["invocations"] == 1 and ops["error_rate"] == 0.0


def test_registry_flow(tmp_path):
    reg = LocalModelRegistry(tmp_path / "reg.json")
    pkg = reg.register("g", ARTIFACT_DIR)
    assert pkg["approval_status"] == PENDING and pkg["validation"]["passed"]
    assert reg.register("g", ARTIFACT_DIR)["model_package_version"] == 1  # idempotente
    with pytest.raises(PermissionError):
        reg.deployment_manifest("g", 1, "staging")
    with pytest.raises(ValueError):
        reg.set_status("g", 1, APPROVED, "x", "curto")
    reg.set_status("g", 1, APPROVED, "revisor", "gates e documentação revisados")
    assert reg.deployment_manifest("g", 1, "staging")["applied"] is False
    with pytest.raises(RuntimeError):
        reg.set_status("g", 1, REJECTED, "revisor", "tentativa de mudar decisão")
    assert LocalModelRegistry(tmp_path / "reg.json").latest_approved("g")["model_package_version"] == 1


def test_registry_gates_block_weak_model(tmp_path):
    with pytest.raises(GateFailed):
        LocalModelRegistry(tmp_path / "r.json").register("g", ARTIFACT_DIR, gates={"gini_min": 0.99, "ece_max": 1,
                                                                                    "psi_train_test_max": 1})


def test_monitoring_stable_batch_is_green_and_shift_is_detected():
    ref = json.loads((ARTIFACT_DIR / "reference_profile.json").read_text(encoding="utf-8"))
    feats = LocalScorer().features
    stable = sample_from_reference(ref, feats, 5000, seed=3)
    assert (drift_report(ref, stable)["psi"] < 0.10).all()
    spec = ref["features"]["PAY_0"]
    shifted = np.clip(stable["PAY_0"].to_numpy() + 2, -2, 8)
    assert psi_against_reference(spec, shifted) > 0.25


def test_canary_rules():
    policy = {"gates": {"max_error_rate": 0.01, "max_p95_latency_ms": 300, "max_score_psi": 0.1,
                        "min_decision_agreement": 0.9, "min_rank_corr": 0.85},
              "rollback_on": ["error_rate", "p95_latency"], "traffic_steps": [10, 50, 100]}
    good = {"score_psi_challenger_vs_champion": 0.02, "decision_agreement": 0.95, "spearman_rank_corr": 0.95}
    assert canary_decision(good, {"error_rate": 0.0, "p95_latency_ms": 50}, policy)["action"] == "promote_next_step"
    assert canary_decision({**good, "decision_agreement": 0.7}, {"error_rate": 0.0, "p95_latency_ms": 50},
                           policy)["action"] == "hold"
    assert canary_decision(good, {"error_rate": 0.05, "p95_latency_ms": 50}, policy)["action"] == "rollback"
