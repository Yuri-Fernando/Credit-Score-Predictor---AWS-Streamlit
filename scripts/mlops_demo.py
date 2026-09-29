#!/usr/bin/env python
"""Demonstração local do fluxo MLOps v3 (sem nenhuma chamada à AWS).

    python scripts/mlops_demo.py     → registry/model_registry.json e reports/mlops/*.json

1. validate + register do champion RiskCredit (PendingManualApproval)
2. aprovação manual (aprovador + motivo) → manifesto de deploy (applied=false)
3. handler v3: golden samples (200), payload com campo ausente (422), campo
   excluído SEX (422), JSON inválido (400), payload gigante (413)
4. monitoramento: lote estável (amostrado do perfil de referência) × tráfego
   sintético com schema UCI (distribuição diferente → drift esperado)
5. shadow: champion × challenger (modelo adversarialmente treinado da V2) → canary
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("INFERENCE_MODE", "local")
os.environ.setdefault("PERSIST", "false")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.adversarial.dataset import FEATURES, load_dataset, split  # noqa: E402
from src.adversarial.model import CreditRiskModel  # noqa: E402
from src.mlops import handler  # noqa: E402
from src.mlops.monitoring import drift_report, operational_metrics, sample_from_reference  # noqa: E402
from src.mlops.registry import APPROVED, LocalModelRegistry  # noqa: E402
from src.mlops.scoring import ARTIFACT_DIR, LocalScorer  # noqa: E402
from src.mlops.shadow import canary_decision, shadow_compare  # noqa: E402

OUT = ROOT / "reports" / "mlops"


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    reg = LocalModelRegistry(ROOT / "registry" / "model_registry.json")
    pkg = reg.register("riskcredit-pd-12m", ARTIFACT_DIR.relative_to(ROOT))
    if pkg["approval_status"] != APPROVED:
        reg.set_status("riskcredit-pd-12m", pkg["model_package_version"], APPROVED, "demo-model-risk-reviewer",
                       "Gates de validação aprovados; model card e limitações revisados (demo).")
    pkg = reg.latest_approved("riskcredit-pd-12m")
    manifest = reg.deployment_manifest("riskcredit-pd-12m", pkg["model_package_version"], "staging")
    print(f"[1-2] registry: v{pkg['model_package_version']} {pkg['approval_status']} gates={pkg['validation']['checks']}")

    golden = json.loads((ARTIFACT_DIR / "golden_samples.json").read_text(encoding="utf-8"))
    handler.LOG_SINK.clear()
    r_ok = handler.lambda_handler({"body": json.dumps({"records": [g["input"] for g in golden]})})
    got = [x["pd"] for x in json.loads(r_ok["body"])["results"]]
    max_diff = float(np.max(np.abs(np.array(got) - np.array([g["expected_pd"] for g in golden]))))
    bad_missing = {k: v for k, v in golden[0]["input"].items() if k != "PAY_0"}
    cases = {
        "campo_ausente": handler.lambda_handler({"body": json.dumps({"data": bad_missing})}),
        "atributo_excluido_SEX": handler.lambda_handler({"body": json.dumps({"data": {**golden[0]["input"], "SEX": 2}})}),
        "json_invalido": handler.lambda_handler({"body": "{nao-json"}),
        "payload_gigante": handler.lambda_handler({"body": json.dumps({"records": [golden[0]["input"]] * 300})}),
    }
    handler_report = {"golden_status": r_ok["statusCode"], "golden_max_abs_diff": max_diff,
                      "negative_cases": {k: {"status": v["statusCode"],
                                             "error": json.loads(v["body"]).get("details", [{}])[0].get("error",
                                                                                                      json.loads(v["body"]).get("error"))}
                                         for k, v in cases.items()},
                      "operational": operational_metrics(handler.LOG_SINK)}
    print(f"[3] handler: golden {r_ok['statusCode']} (máx |Δ PD| = {max_diff:.2e}); negativos "
          f"{ {k: v['status'] for k, v in handler_report['negative_cases'].items()} }")

    scorer = LocalScorer()
    ref = json.loads((ARTIFACT_DIR / "reference_profile.json").read_text(encoding="utf-8"))
    stable = sample_from_reference(ref, scorer.features, 3000, seed=1)
    import xgboost as xgb
    stable["pd"] = scorer.booster.predict(xgb.DMatrix(stable[scorer.features], feature_names=scorer.features))
    synth = load_dataset(n_synth=3000, seed=5)
    traffic = synth[FEATURES].to_dict(orient="records")
    frame = scorer.model_frame(traffic)
    frame["pd"] = scorer.predict_pd(traffic)
    d_stable, d_synth = drift_report(ref, stable), drift_report(ref, frame)
    print(f"[4] drift: estável → {d_stable['alert'].value_counts().to_dict()}; tráfego sintético → "
          f"{d_synth['alert'].value_counts().to_dict()}")

    df = load_dataset(n_synth=4000, seed=42)
    Xtr, ytr, _, _ = split(df, seed=42)
    challenger = CreditRiskModel().fit(Xtr, ytr)
    champ_fn = scorer.predict_pd
    chal_fn = lambda recs: challenger.score(np.array([[r[f] for f in FEATURES] for r in recs]))  # noqa: E731
    sample = traffic[:400]
    shadow = shadow_compare(champ_fn, chal_fn, sample, threshold=0.12)
    policy = yaml.safe_load((ROOT / "configs" / "canary_policy.yaml").read_text(encoding="utf-8"))
    canary_ops = {"error_rate": 0.0, "p95_latency_ms": shadow["p95_latency_ms_challenger"]}
    decision = canary_decision(shadow, canary_ops, policy)
    print(f"[5] shadow: concordância={shadow['decision_agreement']:.3f} PSI={shadow['score_psi_challenger_vs_champion']:.3f} "
          f"→ canary: {decision['action']} (falhas: {decision['failed']})")

    summary = {"registry_package": pkg, "deployment_manifest": manifest, "handler": handler_report,
               "drift_stable": d_stable.round(4).to_dict(orient="records"),
               "drift_synthetic_traffic": d_synth.round(4).to_dict(orient="records"),
               "shadow": shadow, "canary": decision,
               "notes": ["nenhuma chamada AWS foi feita", "tráfego sintético usa o gerador da V2 (schema UCI, "
                         "distribuição diferente do treino) — drift é o resultado esperado",
                         "challenger = modelo adversarialmente treinado da V2 sobre dados sintéticos",
                         "lote estável amostra cada feature de forma independente: marginais ficam verdes, mas o "
                         "score fica vermelho porque a estrutura conjunta (ex.: PAY_0 × max_delay) é destruída — "
                         "drift conjunto que o PSI por feature não detecta e o PSI do score detecta"]}
    (OUT / "mlops_demo_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=float),
                                                 encoding="utf-8")
    return summary


if __name__ == "__main__":
    main()
