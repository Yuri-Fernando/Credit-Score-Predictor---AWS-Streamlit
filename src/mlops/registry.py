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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PENDING, APPROVED, REJECTED = "PendingManualApproval", "Approved", "Rejected"
DEFAULT_GATES = {"gini_min": 0.45, "ece_max": 0.02, "psi_train_test_max": 0.10}

# --- Governança de ciclo de vida (v3.2) ------------------------------------------------------
# Camada opcional sobre o fluxo de aprovação acima. Uma versão só passa a ser "governada"
# (lifecycle.governed = True) na primeira operação de ciclo de vida; versões e manifestos
# anteriores à v3.2 continuam válidos e se comportam exatamente como antes.
(S_VALIDATION, S_REGISTRY, S_RISK, S_APPROVAL, S_SHADOW, S_CANARY, S_PRODUCTION, S_DRIFT, S_REVALIDATION,
 S_RETIREMENT) = LIFECYCLE_STAGES = (
    "Validation", "Registry", "RiskAssessment", "ManualApproval", "Shadow", "Canary", "Production",
    "DriftMonitoring", "Revalidation", "Retirement")
# Retirement é alcançado por ``retire()`` (terminal; nada é apagado). Canary→Shadow = rollback.
# DriftMonitoring é o estado de operação monitorada; sai dele por Revalidation ou Retirement.
# Revalidation→RiskAssessment reabre a aprovação (a decisão anterior permanece no histórico).
LIFECYCLE_TRANSITIONS = {
    S_VALIDATION: {S_REGISTRY},
    S_REGISTRY: {S_RISK},
    S_RISK: {S_APPROVAL},
    S_APPROVAL: {S_SHADOW},
    S_SHADOW: {S_CANARY},
    S_CANARY: {S_PRODUCTION, S_SHADOW},
    S_PRODUCTION: {S_DRIFT},
    S_DRIFT: {S_REVALIDATION},
    S_REVALIDATION: {S_RISK},
    S_RETIREMENT: set(),
}
SERVING_STAGES = {S_SHADOW, S_CANARY, S_PRODUCTION, S_DRIFT}  # estágios que admitem manifesto de deploy
PROMOTIONS = {(S_APPROVAL, S_SHADOW), (S_SHADOW, S_CANARY), (S_CANARY, S_PRODUCTION)}  # exigem revisão em dia
RISK_TIERS = ("LOW", "LIMITED", "HIGH", "PROHIBITED")
DEFAULT_LIFECYCLE_POLICY = {
    "risk_assessment_path": None,          # ex.: ../Risco de Credito/governance/risk_assessment.json
    "risk_tier_field": "risk_tier",
    "review_interval_days": {"LOW": 365, "LIMITED": 180, "HIGH": 90},
    "prohibited_tiers": ["PROHIBITED"],
    "_base_dir": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GateFailed(RuntimeError):
    pass


class LifecycleError(RuntimeError):
    """Operação de ciclo de vida inválida (estágio, pré-condição ou dado ausente)."""


class InvalidTransition(LifecycleError):
    pass


class RiskAssessmentUnavailable(LifecycleError):
    pass


class ReviewOverdue(PermissionError):
    """review_due_date vencida: promoção/deploy bloqueados até nova revalidação."""


def load_lifecycle_policy(path: str | Path) -> dict:
    """Lê ``configs/lifecycle_policy.yaml``; caminhos relativos resolvem a partir da raiz do repo."""
    import yaml
    p = Path(path)
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    policy = {**DEFAULT_LIFECYCLE_POLICY, **cfg}
    policy["review_interval_days"] = {**DEFAULT_LIFECYCLE_POLICY["review_interval_days"],
                                      **(cfg.get("review_interval_days") or {})}
    policy["_base_dir"] = str(p.resolve().parent.parent)
    return policy


class LocalModelRegistry:
    def __init__(self, path: str | Path, policy: dict | None = None):
        self.path = Path(path)
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"groups": {}}
        self.policy = {**DEFAULT_LIFECYCLE_POLICY, **(policy or {})}

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
            "lifecycle": self._new_lifecycle(S_REGISTRY),
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

    def set_status(self, group: str, version: int, status: str, approver: str, reason: str,
                   review_interval_days: int | None = None, today: date | None = None) -> dict:
        if status not in (APPROVED, REJECTED):
            raise ValueError("status deve ser Approved ou Rejected")
        if len(reason.strip()) < 10:
            raise ValueError("motivo da decisão é obrigatório (≥ 10 caracteres)")
        v = self._get(group, version)
        if v["approval_status"] != PENDING:
            raise RuntimeError(f"versão já decidida ({v['approval_status']}) — registre nova versão")
        lc = self._lc(v)
        if lc["governed"]:  # fluxo governado: a decisão acontece no estágio ManualApproval, com tier definido
            if lc["stage"] != S_APPROVAL:
                raise InvalidTransition(f"decisão manual só no estágio {S_APPROVAL} (atual: {lc['stage']})")
            if status == APPROVED and lc["risk_tier"] in self.policy["prohibited_tiers"]:
                raise PermissionError(f"risk_tier {lc['risk_tier']} não pode ser aprovado")
        v["approval_status"] = status
        v["history"].append({"at": _now(), "event": "decision", "status": status, "approver": approver,
                             "reason": reason})
        if lc["governed"] and status == APPROVED:
            self._schedule_review(v, lc, self._today(today), review_interval_days)
        elif lc["governed"] and status == REJECTED:  # rejeição governada encerra a versão (histórico preservado)
            lc["stage"], lc["retired_at"] = S_RETIREMENT, _now()
            self._event(v, "lifecycle", **{"from": S_APPROVAL, "to": S_RETIREMENT, "actor": approver,
                                           "reason": f"rejeitada: {reason}"})
        self._save()
        return v

    def latest_approved(self, group: str) -> dict | None:
        ok = [v for v in self.state["groups"].get(group, {}).get("versions", [])
              if v["approval_status"] == APPROVED and self._lc(v)["stage"] != S_RETIREMENT]
        return ok[-1] if ok else None

    def deployment_manifest(self, group: str, version: int, stage: str, today: date | None = None) -> dict:
        """Manifesto de deploy (NÃO aplicado): só versões aprovadas.

        Versões governadas (v3.2) exigem também estágio de serviço (Shadow/Canary/Production/DriftMonitoring),
        não-aposentadas e com revisão em dia.
        """
        v = self._get(group, version)
        if v["approval_status"] != APPROVED:
            raise PermissionError("deploy exige versão Approved")
        lc = self._lc(v)
        extra: dict = {}
        if lc["governed"]:
            if lc["stage"] == S_RETIREMENT:
                raise PermissionError("versão aposentada (Retirement) não pode ser implantada")
            if lc["stage"] not in SERVING_STAGES:
                raise InvalidTransition(f"deploy exige estágio {sorted(SERVING_STAGES)} (atual: {lc['stage']})")
            self._assert_review_current(lc, today)
            extra = {"lifecycle": {k: lc[k] for k in ("stage", "risk_tier", "model_owner", "business_owner",
                                                      "approval_date", "review_due_date")}}
        return {"stage": stage, "model_package_group": group, "model_package_version": version,
                "artifact_sha256": v["artifact_sha256"], "container": "sagemaker-xgboost:1.7-1",
                "data_capture": {"enabled": True, "sampling_percentage": 100},
                "applied": False, "note": "deploy real pendente (custo AWS) — ver ROADMAP", **extra}

    # ------------------------------------------------------------------ ciclo de vida (v3.2)
    @staticmethod
    def _new_lifecycle(stage: str, governed: bool = False) -> dict:
        return {"governed": governed, "stage": stage, "model_owner": None, "business_owner": None,
                "risk_tier": None, "risk_assessment_source": None, "approval_date": None,
                "review_due_date": None, "review_interval_days": None, "retired_at": None}

    def _lc(self, v: dict) -> dict:
        """Bloco de ciclo de vida da versão; manifestos anteriores à v3.2 ganham o default inferido (não governado).

        Inferência: Pending→Registry, Approved→Registry (ainda sem avaliação de risco/responsáveis: a
        governança começa em assess_risk e a revisão é agendada ao sair de ManualApproval), Rejected→Retirement.
        """
        lc = v.get("lifecycle")
        if lc is None:
            stage = S_RETIREMENT if v.get("approval_status") == REJECTED else S_REGISTRY
            lc = v["lifecycle"] = self._new_lifecycle(stage)
        return lc

    @staticmethod
    def _today(today: date | None) -> date:
        return today or date.today()

    def _schedule_review(self, v: dict, lc: dict, d0: date, interval_days: int | None = None) -> None:
        """Define approval_date e review_due_date (intervalo por risk_tier na política, ou o informado)."""
        days = int(interval_days or self.policy["review_interval_days"].get(lc["risk_tier"], 180))
        lc["approval_date"] = d0.isoformat()
        lc["review_due_date"] = (d0 + timedelta(days=days)).isoformat()
        lc["review_interval_days"] = days
        self._event(v, "review_scheduled", approval_date=lc["approval_date"], review_due_date=lc["review_due_date"],
                    review_interval_days=days)

    def _assert_review_current(self, lc: dict, today: date | None = None) -> None:
        due = lc.get("review_due_date")
        if due and date.fromisoformat(due) < self._today(today):
            raise ReviewOverdue(f"revisão vencida em {due}: nova revalidação é necessária antes de promover/implantar")

    def _event(self, v: dict, event: str, **fields) -> None:
        v["history"].append({"at": _now(), "event": event, **fields})

    def _gov(self, group: str, version: int) -> tuple[dict, dict]:
        v = self._get(group, version)
        lc = self._lc(v)
        if lc["stage"] == S_RETIREMENT:
            raise InvalidTransition("versão aposentada (Retirement) é terminal")
        lc["governed"] = True
        return v, lc

    @staticmethod
    def _check_actor(actor: str, reason: str) -> None:
        if not actor or not actor.strip():
            raise ValueError("actor é obrigatório")
        if len(reason.strip()) < 10:
            raise ValueError("motivo é obrigatório (≥ 10 caracteres)")

    def lifecycle(self, group: str, version: int) -> dict:
        """Cópia do bloco de ciclo de vida (somente leitura)."""
        return dict(self._lc(self._get(group, version)))

    def set_owners(self, group: str, version: int, model_owner: str, business_owner: str, actor: str) -> dict:
        if not (model_owner or "").strip() or not (business_owner or "").strip():
            raise ValueError("model_owner e business_owner são obrigatórios")
        v, lc = self._gov(group, version)
        lc["model_owner"], lc["business_owner"] = model_owner.strip(), business_owner.strip()
        self._event(v, "owners_set", actor=actor, model_owner=lc["model_owner"], business_owner=lc["business_owner"])
        self._save()
        return dict(lc)

    def assess_risk(self, group: str, version: int, actor: str, risk_tier: str | None = None,
                    assessment_path: str | Path | None = None) -> dict:
        """Define o risk_tier da versão (estágio RiskAssessment).

        ``risk_tier`` explícito tem prioridade. Sem ele, lê o tier de um ``risk_assessment.json`` (caminho
        passado ou ``risk_assessment_path`` da política), conferindo que a avaliação é do mesmo modelo/versão.
        """
        v, lc = self._gov(group, version)
        if lc["stage"] != S_RISK:
            raise InvalidTransition(f"assess_risk exige estágio {S_RISK} (atual: {lc['stage']})")
        source = None
        if risk_tier is None:
            risk_tier, source = self._tier_from_file(v, assessment_path)
        risk_tier = str(risk_tier).upper()
        if risk_tier not in RISK_TIERS:
            raise ValueError(f"risk_tier inválido: {risk_tier} (use {RISK_TIERS})")
        lc["risk_tier"], lc["risk_assessment_source"] = risk_tier, source
        self._event(v, "risk_assessed", actor=actor, risk_tier=risk_tier, source=source)
        self._save()
        return dict(lc)

    def _tier_from_file(self, v: dict, assessment_path) -> tuple[str, dict]:
        raw = assessment_path or self.policy.get("risk_assessment_path")
        if not raw:
            raise RiskAssessmentUnavailable("sem risk_tier explícito e sem caminho de avaliação (política/argumento)")
        p = Path(raw)
        if not p.is_absolute():
            base = Path(self.policy["_base_dir"]) if self.policy.get("_base_dir") else self.path.parent
            p = (base / p)
        if not p.exists():
            raise RiskAssessmentUnavailable(f"avaliação de risco não encontrada: {p}")
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            raise RiskAssessmentUnavailable(f"avaliação de risco ilegível ({p.name}): {e}") from e
        field = self.policy.get("risk_tier_field", "risk_tier")
        if field not in doc:
            raise RiskAssessmentUnavailable(f"campo '{field}' ausente em {p.name}")
        if doc.get("model_version") and doc["model_version"] != v.get("source_model_version"):
            raise RiskAssessmentUnavailable(
                f"avaliação é da versão {doc['model_version']}, o registry tem {v.get('source_model_version')}")
        return str(doc[field]).upper(), {"path": p.as_posix(), "sha256": sha256(p), "model": doc.get("model"),
                                         "model_version": doc.get("model_version"),
                                         "generated_at": doc.get("generated_at")}

    def advance(self, group: str, version: int, to_stage: str, actor: str, reason: str,
                today: date | None = None) -> dict:
        """Avança um estágio do ciclo de vida, aplicando as pré-condições de cada transição."""
        self._check_actor(actor, reason)
        if to_stage == S_RETIREMENT:
            return self.retire(group, version, actor, reason)
        if to_stage not in LIFECYCLE_STAGES:
            raise ValueError(f"estágio desconhecido: {to_stage}")
        v, lc = self._gov(group, version)
        frm = lc["stage"]
        if to_stage not in LIFECYCLE_TRANSITIONS[frm]:
            raise InvalidTransition(f"transição inválida {frm} → {to_stage} (permitidas: "
                                    f"{sorted(LIFECYCLE_TRANSITIONS[frm])})")
        prohibited = lc["risk_tier"] in self.policy["prohibited_tiers"]
        if frm == S_RISK:  # RiskAssessment → ManualApproval
            if not lc["risk_tier"]:
                raise LifecycleError("risk_tier não definido: execute assess_risk antes de avançar")
            if prohibited:
                raise PermissionError(f"risk_tier {lc['risk_tier']} bloqueia o avanço; só Retirement é possível")
        if frm == S_APPROVAL:  # ManualApproval → Shadow
            if v["approval_status"] != APPROVED:
                raise PermissionError("avanço exige decisão manual Approved (set_status)")
            if not lc["model_owner"] or not lc["business_owner"]:
                raise LifecycleError("model_owner e business_owner são obrigatórios (set_owners)")
            if not lc["review_due_date"]:  # versão aprovada antes da v3.2: agenda a revisão ao entrar na governança
                self._schedule_review(v, lc, self._today(today))
        if (frm, to_stage) in PROMOTIONS:  # promoção: a revisão precisa estar em dia (rollback Canary→Shadow não)
            self._assert_review_current(lc, today)
        if frm == S_REVALIDATION:  # reabre a aprovação; a decisão anterior permanece no histórico
            self._event(v, "revalidation_reopened", actor=actor, reason=reason,
                        previous_approval_date=lc["approval_date"], previous_review_due_date=lc["review_due_date"],
                        previous_status=v["approval_status"])
            v["approval_status"] = PENDING
            lc["approval_date"] = lc["review_due_date"] = lc["review_interval_days"] = None
            lc["risk_tier"], lc["risk_assessment_source"] = None, None  # reavaliar risco no novo ciclo
        lc["stage"] = to_stage
        self._event(v, "lifecycle", **{"from": frm, "to": to_stage, "actor": actor, "reason": reason})
        self._save()
        return dict(lc)

    def retire(self, group: str, version: int, actor: str, reason: str) -> dict:
        """Aposenta a versão (terminal). Nada é apagado: histórico, métricas e hashes permanecem."""
        self._check_actor(actor, reason)
        v, lc = self._gov(group, version)
        frm = lc["stage"]
        lc["stage"], lc["retired_at"] = S_RETIREMENT, _now()
        self._event(v, "lifecycle", **{"from": frm, "to": S_RETIREMENT, "actor": actor, "reason": reason})
        self._save()
        return dict(lc)

    def review_status(self, group: str, version: int, today: date | None = None) -> dict:
        lc = self._lc(self._get(group, version))
        due = lc.get("review_due_date")
        if not due:
            return {"review_due_date": None, "overdue": False, "days_to_due": None, "stage": lc["stage"]}
        days = (date.fromisoformat(due) - self._today(today)).days
        return {"review_due_date": due, "overdue": days < 0 and lc["stage"] != S_RETIREMENT, "days_to_due": days,
                "stage": lc["stage"]}

    def overdue_reviews(self, today: date | None = None) -> list[dict]:
        """Versões governadas, não aposentadas, com revisão vencida — sinal para a revalidação."""
        out = []
        for group, g in self.state["groups"].items():
            for v in g["versions"]:
                lc = self._lc(v)
                if lc["governed"] and lc["stage"] != S_RETIREMENT:
                    st = self.review_status(group, v["model_package_version"], today)
                    if st["overdue"]:
                        out.append({"group": group, "version": v["model_package_version"], **st})
        return out
