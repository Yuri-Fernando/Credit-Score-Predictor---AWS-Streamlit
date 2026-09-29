"""Model Registry local com a semântica do SageMaker Model Registry (plano §5.2).

Fluxo: train (RiskCredit) → validate (gates) → register (PendingManualApproval)
→ approve/reject manual (aprovador + motivo) → deployment manifest (só Approved).
Mesmos nomes de status do SageMaker (``ModelApprovalStatus``) para que a troca
por ``boto3.client("sagemaker").create_model_package`` seja direta — essa troca
fica no ROADMAP por custo. Persistência: JSON append-only com histórico.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PENDING, APPROVED, REJECTED = "PendingManualApproval", "Approved", "Rejected"
DEFAULT_GATES = {"gini_min": 0.45, "ece_max": 0.02, "psi_train_test_max": 0.10}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GateFailed(RuntimeError):
    pass


class LocalModelRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"groups": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def validate(metrics: dict, gates: dict = DEFAULT_GATES) -> dict:
        t = metrics["test"]
        checks = {"gini": t["gini"] >= gates["gini_min"], "ece": t["ece"] <= gates["ece_max"],
                  "psi_train_test": t["psi_train_test"] < gates["psi_train_test_max"]}
        return {"passed": all(checks.values()), "checks": checks, "gates": gates}

    def register(self, group: str, artifact_dir: str | Path, gates: dict = DEFAULT_GATES) -> dict:
        d = Path(artifact_dir)
        card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
        metrics = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        val = self.validate(metrics, gates)
        if not val["passed"]:
            raise GateFailed(f"gates de validação reprovados: {val['checks']}")
        g = self.state["groups"].setdefault(group, {"versions": []})
        art_hash = sha256(d / "xgboost-model.json")
        for v in g["versions"]:
            if v["artifact_sha256"] == art_hash:
                return v  # idempotente: mesmo artefato não gera nova versão
        pkg = {
            "model_package_version": len(g["versions"]) + 1,
            "model_package_group": group,
            "source_model_version": card["version"],
            "champion": card["champion"],
            "artifact_uri": str(d.as_posix()),
            "artifact_sha256": art_hash,
            "training_data_sha256": card["training_data"]["sha256"],
            "metrics": {k: metrics["test"][k] for k in ("auc", "gini", "ks", "brier", "ece", "psi_train_test")},
            "validation": val,
            "approval_status": PENDING,
            "history": [{"at": _now(), "event": "registered", "status": PENDING}],
        }
        g["versions"].append(pkg)
        self._save()
        return pkg

    def _get(self, group: str, version: int) -> dict:
        for v in self.state["groups"][group]["versions"]:
            if v["model_package_version"] == version:
                return v
        raise KeyError(f"{group} v{version} inexistente")

    def set_status(self, group: str, version: int, status: str, approver: str, reason: str) -> dict:
        if status not in (APPROVED, REJECTED):
            raise ValueError("status deve ser Approved ou Rejected")
        if len(reason.strip()) < 10:
            raise ValueError("motivo da decisão é obrigatório (≥ 10 caracteres)")
        v = self._get(group, version)
        if v["approval_status"] != PENDING:
            raise RuntimeError(f"versão já decidida ({v['approval_status']}) — registre nova versão")
        v["approval_status"] = status
        v["history"].append({"at": _now(), "event": "decision", "status": status, "approver": approver,
                             "reason": reason})
        self._save()
        return v

    def latest_approved(self, group: str) -> dict | None:
        ok = [v for v in self.state["groups"].get(group, {}).get("versions", []) if v["approval_status"] == APPROVED]
        return ok[-1] if ok else None

    def deployment_manifest(self, group: str, version: int, stage: str) -> dict:
        """Manifesto de deploy (NÃO aplicado): só versões aprovadas."""
        v = self._get(group, version)
        if v["approval_status"] != APPROVED:
            raise PermissionError("deploy exige versão Approved")
        return {"stage": stage, "model_package_group": group, "model_package_version": version,
                "artifact_sha256": v["artifact_sha256"], "container": "sagemaker-xgboost:1.7-1",
                "data_capture": {"enabled": True, "sampling_percentage": 100},
                "applied": False, "note": "deploy real pendente (custo AWS) — ver ROADMAP"}
