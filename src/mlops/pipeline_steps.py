"""Steps do pipeline de orquestração (plano §5.1 — Step Functions) como funções puras.

Cada função abaixo é compatível com a assinatura de handler de uma Lambda
(``event, context=None -> dict``) e corresponde a um estado ``Task`` do
state machine definido em ``infra/terraform/templates/pipeline.asl.json.tftpl``.
Comunicação é só JSON (dict/list/str/number) — nada de callables cruzando a
"fronteira" do estado, igual ao mundo real de Step Functions.

Fluxo: ValidateBatch → ScoreShadow (Parallel: ScoreChampion/ScoreChallenger)
→ CombineShadow → MonitorDrift → Choice (rollback / hold por drift / hold por
canary / promote) → PublishManifest. Nenhuma etapa chama a AWS: o champion é
o artefato local do RiskCredit (``model_artifacts/riskcredit-v3``); o
challenger usa o mesmo artefato quando nenhum challenger foi aprovado no
registry (fallback documentado — shadow fica trivialmente "concordância 100%"
até existir um challenger real aprovado).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.mlops.contract import FeatureContract
from src.mlops.monitoring import drift_report
from src.mlops.registry import LocalModelRegistry
from src.mlops.scoring import ARTIFACT_DIR, LocalScorer
from src.mlops.shadow import canary_decision, shadow_compare_arrays

ROOT = Path(__file__).resolve().parents[2]
CHAMPION_DIR = ARTIFACT_DIR
CHALLENGER_DIR = CHAMPION_DIR.parent / "riskcredit-v3-challenger"
REGISTRY_PATH = ROOT / "registry" / "model_registry.json"
CANARY_POLICY_PATH = ROOT / "configs" / "canary_policy.yaml"


class PipelineError(RuntimeError):
    """Erro de negócio do pipeline (contrato violado, sem versão aprovada etc.).

    Mapeado para o ``Catch`` dos estados Task no ASL — nunca é uma falha de
    infraestrutura (essas ficam para ``Retry`` no runtime real da AWS).
    """


def _artifact_dir(tag: str) -> Path:
    if tag == "challenger" and CHALLENGER_DIR.exists():
        return CHALLENGER_DIR
    return CHAMPION_DIR


def validate_batch(event: dict, context: Any = None) -> dict:
    """Task 1 — valida o lote contra o contrato do RiskCredit (plano §5.6)."""
    contract = FeatureContract.from_file(CHAMPION_DIR / "feature_schema.json")
    records = event["records"]
    if not isinstance(records, list) or not records:
        raise PipelineError(json.dumps({"stage": "validate_batch", "error": "records_deve_ser_lista_nao_vazia"}))
    errors = [e for i, r in enumerate(records) for e in contract.validate_record(r, i)]
    if errors:
        raise PipelineError(json.dumps({"stage": "validate_batch", "errors": errors[:20]}))
    return {"records": records, "stage": "validated"}


def score_batch(event: dict, context: Any = None) -> dict:
    """Task 2 (um branch do Parallel ``ScoreShadow``) — inferência local.

    ``event["artifact_dir"]`` é ``"champion"`` ou ``"challenger"``; usa o
    mesmo artefato que seria publicado no endpoint SageMaker.
    """
    tag = event.get("artifact_dir", "champion")
    scorer = LocalScorer(_artifact_dir(tag))
    records = event["records"]
    pds = scorer.predict_pd(records).tolist()
    frame = scorer.model_frame(records).copy()
    frame["pd"] = pds
    return {
        "pds": pds,
        "frame": frame.to_dict(orient="records"),
        "model_version": scorer.model_version,
        "artifact_dir": tag,
    }


def combine_shadow(event: dict, context: Any = None) -> dict:
    """Task 3 — combina os dois branches do Parallel em métricas de shadow + decisão de canary (plano §5.4)."""
    import yaml

    champion_out, challenger_out = event["shadow_branches"]
    policy = yaml.safe_load(CANARY_POLICY_PATH.read_text(encoding="utf-8"))
    shadow = shadow_compare_arrays(
        champion_out["pds"], challenger_out["pds"], threshold=event.get("threshold", 0.12)
    )
    canary_ops = {"error_rate": event.get("error_rate", 0.0), "p95_latency_ms": event.get("p95_latency_ms", 0.0)}
    decision = canary_decision(shadow, canary_ops, policy)
    return {
        "records": event["records"],
        "champion": champion_out,
        "challenger": challenger_out,
        "shadow": shadow,
        "decision": decision,
        "stage": "shadow_evaluated",
    }


def monitor_drift(event: dict, context: Any = None) -> dict:
    """Task 4 — PSI do lote (features + score) do champion contra o perfil de referência (plano §5.5)."""
    reference = json.loads((CHAMPION_DIR / "reference_profile.json").read_text(encoding="utf-8"))
    frame = pd.DataFrame(event["champion"]["frame"])
    report = drift_report(reference, frame)
    alerts = report["alert"].value_counts().to_dict()
    return {
        **event,
        "drift_alerts": alerts,
        "drift_red": alerts.get("red", 0) > 0,
        "stage": "monitored",
    }


def publish_manifest(event: dict, context: Any = None) -> dict:
    """Task 5 — manifesto de deploy (plano §5.2/5.3). NUNCA aplica — ``applied`` fica ``false``."""
    registry = LocalModelRegistry(REGISTRY_PATH)
    group = event.get("model_package_group", "riskcredit-pd-12m")
    pkg = registry.latest_approved(group)
    if pkg is None:
        raise PipelineError(json.dumps({"stage": "publish_manifest", "error": "sem_versao_aprovada", "group": group}))
    manifest = registry.deployment_manifest(group, pkg["model_package_version"], event.get("stage_name", "staging"))
    return {**event, "manifest": manifest, "stage": "published_manifest"}
