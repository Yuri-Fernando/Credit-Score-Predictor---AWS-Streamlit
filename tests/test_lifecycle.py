"""Testes da governança de ciclo de vida do registry local (v3.2).

Nenhum teste chama a AWS. Datas são injetadas (``today``) — nada depende do relógio."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mlops.registry import (  # noqa: E402
    APPROVED, LIFECYCLE_STAGES, LIFECYCLE_TRANSITIONS, PENDING, REJECTED, InvalidTransition, LifecycleError,
    LocalModelRegistry, ReviewOverdue, RiskAssessmentUnavailable, load_lifecycle_policy)
from src.mlops.scoring import ARTIFACT_DIR  # noqa: E402

T0 = date(2026, 10, 21)
G = "g"
WHY = "motivo suficiente para a trilha"


def _reg(tmp_path, policy=None):
    reg = LocalModelRegistry(tmp_path / "reg.json", policy=policy)
    reg.register(G, ARTIFACT_DIR)
    return reg


def _to_manual_approval(reg, tier="HIGH"):
    reg.set_owners(G, 1, "ana.modelos", "beto.negocio", "ana")
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    reg.assess_risk(G, 1, "ana", risk_tier=tier)
    return reg.advance(G, 1, "ManualApproval", "ana", WHY)


def _approved_in_shadow(reg, tier="HIGH", today=T0):
    _to_manual_approval(reg, tier)
    reg.set_status(G, 1, APPROVED, "revisor", "gates e risco revisados", today=today)
    return reg.advance(G, 1, "Shadow", "ana", WHY, today=today)


# ---------------------------------------------------------------- transições
def test_full_lifecycle_happy_path_and_audit_trail(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg)
    for stage in ("Canary", "Production", "DriftMonitoring", "Revalidation", "RiskAssessment"):
        reg.advance(G, 1, stage, "ana", WHY, today=T0)
    lc = reg.lifecycle(G, 1)
    assert lc["stage"] == "RiskAssessment" and lc["governed"] is True
    path = [(h["from"], h["to"]) for h in reg.state["groups"][G]["versions"][0]["history"] if h["event"] == "lifecycle"]
    assert path[0] == ("Registry", "RiskAssessment") and path[-1] == ("Revalidation", "RiskAssessment")
    assert all("actor" in h and "reason" in h for h in reg.state["groups"][G]["versions"][0]["history"]
               if h["event"] == "lifecycle")


@pytest.mark.parametrize("frm,to", [
    ("Registry", "Shadow"), ("Registry", "Production"), ("RiskAssessment", "Canary"), ("ManualApproval", "Production"),
    ("Shadow", "Production"), ("Production", "Canary"), ("DriftMonitoring", "Production"),
])
def test_invalid_transitions_are_rejected(frm, to):
    assert to not in LIFECYCLE_TRANSITIONS[frm]


def test_cannot_skip_stages_via_advance(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(InvalidTransition):
        reg.advance(G, 1, "Production", "ana", WHY)
    with pytest.raises(InvalidTransition):
        reg.advance(G, 1, "Shadow", "ana", WHY)
    assert reg.lifecycle(G, 1)["stage"] == "Registry"  # estado intacto após a recusa


def test_actor_and_reason_are_mandatory(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(ValueError):
        reg.advance(G, 1, "RiskAssessment", "ana", "curto")
    with pytest.raises(ValueError):
        reg.advance(G, 1, "RiskAssessment", "", WHY)


def test_stage_catalog_matches_documented_chain():
    assert LIFECYCLE_STAGES == ("Validation", "Registry", "RiskAssessment", "ManualApproval", "Shadow", "Canary",
                                "Production", "DriftMonitoring", "Revalidation", "Retirement")


# ---------------------------------------------------------------- pré-condições
def test_advance_to_manual_approval_requires_risk_tier(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    with pytest.raises(LifecycleError, match="risk_tier"):
        reg.advance(G, 1, "ManualApproval", "ana", WHY)


def test_shadow_requires_owners_and_manual_approval(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    reg.assess_risk(G, 1, "ana", risk_tier="LIMITED")
    reg.advance(G, 1, "ManualApproval", "ana", WHY)
    with pytest.raises(PermissionError, match="Approved"):
        reg.advance(G, 1, "Shadow", "ana", WHY)
    reg.set_status(G, 1, APPROVED, "revisor", "gates e risco revisados", today=T0)
    with pytest.raises(LifecycleError, match="model_owner"):
        reg.advance(G, 1, "Shadow", "ana", WHY, today=T0)
    reg.set_owners(G, 1, "ana.modelos", "beto.negocio", "ana")
    assert reg.advance(G, 1, "Shadow", "ana", WHY, today=T0)["stage"] == "Shadow"


def test_owners_are_required_values(tmp_path):
    with pytest.raises(ValueError):
        _reg(tmp_path).set_owners(G, 1, "ana", "  ", "ana")


def test_prohibited_tier_blocks_approval_and_advance(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    reg.assess_risk(G, 1, "ana", risk_tier="prohibited")  # normaliza para maiúsculas
    with pytest.raises(PermissionError, match="PROHIBITED"):
        reg.advance(G, 1, "ManualApproval", "ana", WHY)
    reg.retire(G, 1, "ana", "uso proibido pela avaliação de risco")  # único caminho possível
    assert reg.lifecycle(G, 1)["stage"] == "Retirement"


def test_governed_decision_only_at_manual_approval(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    with pytest.raises(InvalidTransition):
        reg.set_status(G, 1, APPROVED, "revisor", "tentativa fora do estágio")


def test_invalid_tier_is_rejected(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    with pytest.raises(ValueError):
        reg.assess_risk(G, 1, "ana", risk_tier="MEDIO")


def test_governed_rejection_retires_and_keeps_history(tmp_path):
    reg = _reg(tmp_path)
    _to_manual_approval(reg)
    reg.set_status(G, 1, REJECTED, "revisor", "AIR abaixo do limiar sem mitigação")
    assert reg.lifecycle(G, 1)["stage"] == "Retirement"
    hist = reg.state["groups"][G]["versions"][0]["history"]
    assert [h["event"] for h in hist][0] == "registered" and hist[-1]["to"] == "Retirement"


# ---------------------------------------------------------------- vencimento
def test_review_due_date_follows_tier_interval(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg, tier="HIGH", today=T0)
    lc = reg.lifecycle(G, 1)
    assert lc["approval_date"] == "2026-10-21" and lc["review_due_date"] == "2027-01-19"  # +90 dias
    assert lc["review_interval_days"] == 90


def test_interval_override_and_policy_per_tier(tmp_path):
    reg = LocalModelRegistry(tmp_path / "r.json", policy={"review_interval_days": {"LOW": 30}})
    reg.register(G, ARTIFACT_DIR)
    _to_manual_approval(reg, tier="LOW")
    reg.set_status(G, 1, APPROVED, "revisor", "gates e risco revisados", today=T0)
    assert reg.lifecycle(G, 1)["review_due_date"] == "2026-11-20"


def test_overdue_review_blocks_promotion_but_not_rollback(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg, today=T0)
    late = date(2027, 1, 20)  # 1 dia depois do vencimento
    with pytest.raises(ReviewOverdue):
        reg.advance(G, 1, "Canary", "ana", WHY, today=late)
    assert reg.lifecycle(G, 1)["stage"] == "Shadow"
    reg.advance(G, 1, "Canary", "ana", WHY, today=date(2027, 1, 19))  # no dia ainda vale
    reg.advance(G, 1, "Shadow", "ana", "rollback do canary por métricas", today=late)  # rollback não é bloqueado
    assert reg.lifecycle(G, 1)["stage"] == "Shadow"


def test_overdue_review_blocks_deployment_manifest(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg, today=T0)
    assert reg.deployment_manifest(G, 1, "staging", today=T0)["lifecycle"]["stage"] == "Shadow"
    with pytest.raises(ReviewOverdue):
        reg.deployment_manifest(G, 1, "staging", today=date(2027, 2, 1))


def test_overdue_reviews_signal_lists_only_governed_active_versions(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg, today=T0)
    assert reg.overdue_reviews(today=T0) == []
    due = reg.overdue_reviews(today=date(2027, 3, 1))
    assert len(due) == 1 and due[0]["version"] == 1 and due[0]["overdue"] is True and due[0]["days_to_due"] < 0
    reg.retire(G, 1, "ana", "substituído por nova versão")
    assert reg.overdue_reviews(today=date(2027, 3, 1)) == []  # aposentada não exige revisão


def test_revalidation_reopens_approval_and_preserves_prior_decision(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg, today=T0)
    for stage in ("Canary", "Production", "DriftMonitoring", "Revalidation"):
        reg.advance(G, 1, stage, "ana", WHY, today=T0)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    v = reg.state["groups"][G]["versions"][0]
    assert v["approval_status"] == PENDING and reg.lifecycle(G, 1)["review_due_date"] is None
    reopened = [h for h in v["history"] if h["event"] == "revalidation_reopened"][0]
    assert reopened["previous_status"] == APPROVED and reopened["previous_review_due_date"] == "2027-01-19"
    # novo ciclo exige novo tier e nova decisão
    reg.assess_risk(G, 1, "ana", risk_tier="LIMITED")
    reg.advance(G, 1, "ManualApproval", "ana", WHY)
    reg.set_status(G, 1, APPROVED, "revisor", "revalidado após drift", today=date(2027, 2, 1))
    assert reg.lifecycle(G, 1)["review_due_date"] == "2027-07-31"  # LIMITED = 180 dias


# ---------------------------------------------------------------- retirement
def test_retirement_is_terminal_and_never_deletes(tmp_path):
    reg = _reg(tmp_path)
    _approved_in_shadow(reg)
    before = json.dumps(reg.state["groups"][G]["versions"][0]["metrics"], sort_keys=True)
    reg.retire(G, 1, "ana", "substituído por nova versão")
    lc = reg.lifecycle(G, 1)
    assert lc["stage"] == "Retirement" and lc["retired_at"]
    v = reg.state["groups"][G]["versions"][0]
    assert json.dumps(v["metrics"], sort_keys=True) == before  # dados da versão preservados
    assert len(reg.state["groups"][G]["versions"]) == 1
    assert v["history"][0]["event"] == "registered"
    with pytest.raises(InvalidTransition):
        reg.advance(G, 1, "Canary", "ana", WHY)
    with pytest.raises(InvalidTransition):
        reg.retire(G, 1, "ana", "segunda aposentadoria")
    with pytest.raises(PermissionError, match="aposentada"):
        reg.deployment_manifest(G, 1, "staging")
    assert reg.latest_approved(G) is None  # aposentada sai de latest_approved, mas continua no registro


def test_retirement_survives_reload(tmp_path):
    reg = _reg(tmp_path)
    reg.retire(G, 1, "ana", "descontinuada antes da aprovação")
    again = LocalModelRegistry(tmp_path / "reg.json")
    assert again.lifecycle(G, 1)["stage"] == "Retirement"
    assert again.state["groups"][G]["versions"][0]["history"][-1]["to"] == "Retirement"


# ---------------------------------------------------------------- compatibilidade
def _legacy_registry(tmp_path, status=APPROVED):
    """Registry gravado pela v3.0/3.1: sem bloco ``lifecycle``."""
    new = _reg(tmp_path)
    v = new.state["groups"][G]["versions"][0]
    v.pop("lifecycle")
    v["approval_status"] = status
    (tmp_path / "legacy.json").write_text(json.dumps(new.state), encoding="utf-8")
    assert "lifecycle" not in json.loads((tmp_path / "legacy.json").read_text(encoding="utf-8"))["groups"][G][
        "versions"][0]
    return LocalModelRegistry(tmp_path / "legacy.json")


def test_legacy_manifest_still_valid_and_not_governed(tmp_path):
    reg = _legacy_registry(tmp_path)
    assert reg.latest_approved(G)["model_package_version"] == 1
    manifest = reg.deployment_manifest(G, 1, "staging")  # comportamento anterior: só exige Approved
    assert manifest["applied"] is False and "lifecycle" not in manifest
    assert reg.lifecycle(G, 1)["governed"] is False and reg.lifecycle(G, 1)["stage"] == "Registry"
    assert reg.review_status(G, 1)["overdue"] is False and reg.overdue_reviews() == []


def test_legacy_pending_can_still_be_decided_the_old_way(tmp_path):
    reg = _legacy_registry(tmp_path, status=PENDING)
    reg.set_status(G, 1, APPROVED, "revisor", "gates e documentação revisados")
    assert reg.lifecycle(G, 1)["review_due_date"] is None  # sem opt-in, nada de revisão agendada
    assert reg.deployment_manifest(G, 1, "staging")["applied"] is False


def test_legacy_approved_version_can_enter_governance(tmp_path):
    reg = _legacy_registry(tmp_path)
    reg.set_owners(G, 1, "ana.modelos", "beto.negocio", "ana")
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    reg.assess_risk(G, 1, "ana", risk_tier="HIGH")
    reg.advance(G, 1, "ManualApproval", "ana", WHY)
    reg.advance(G, 1, "Shadow", "ana", WHY, today=T0)  # já Approved: a revisão é agendada na entrada
    assert reg.lifecycle(G, 1)["review_due_date"] == "2027-01-19"
    ev = [h["event"] for h in reg.state["groups"][G]["versions"][0]["history"]]
    assert "review_scheduled" in ev


def test_legacy_rejected_is_inferred_terminal(tmp_path):
    reg = _legacy_registry(tmp_path, status=REJECTED)
    assert reg.lifecycle(G, 1)["stage"] == "Retirement"


def test_governed_deploy_requires_serving_stage(tmp_path):
    reg = _reg(tmp_path)
    _to_manual_approval(reg)
    reg.set_status(G, 1, APPROVED, "revisor", "gates e risco revisados", today=T0)
    with pytest.raises(InvalidTransition, match="deploy exige estágio"):
        reg.deployment_manifest(G, 1, "staging", today=T0)


# ---------------------------------------------------------------- risk_tier vindo de arquivo
def _assessment(tmp_path, tier="HIGH", model_version="v3-20260929", name="risk_assessment.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"schema_version": "risk-assessment/1.0", "model": "riskcredit-pd-12m",
                             "model_version": model_version, "risk_tier": tier, "generated_at": "2026-10-20"}),
                 encoding="utf-8")
    return p


def test_risk_tier_read_from_file_with_provenance(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    p = _assessment(tmp_path, tier="high")
    lc = reg.assess_risk(G, 1, "ana", assessment_path=p)
    assert lc["risk_tier"] == "HIGH"
    src = lc["risk_assessment_source"]
    assert src["model_version"] == "v3-20260929" and len(src["sha256"]) == 64 and src["path"].endswith(p.name)


def test_risk_tier_path_comes_from_policy_not_code(tmp_path):
    cfg = tmp_path / "configs"
    cfg.mkdir()
    (cfg / "lifecycle_policy.yaml").write_text(
        "risk_assessment_path: gov/risk_assessment.json\nreview_interval_days: {HIGH: 45}\n", encoding="utf-8")
    (tmp_path / "gov").mkdir()
    _assessment(tmp_path / "gov", tier="LIMITED")
    policy = load_lifecycle_policy(cfg / "lifecycle_policy.yaml")
    assert policy["review_interval_days"]["HIGH"] == 45 and policy["review_interval_days"]["LOW"] == 365  # mescla
    reg = LocalModelRegistry(tmp_path / "reg.json", policy=policy)
    reg.register(G, ARTIFACT_DIR)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    assert reg.assess_risk(G, 1, "ana")["risk_tier"] == "LIMITED"  # sem tier explícito: lê do arquivo da política


def test_explicit_tier_has_priority_over_file(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    lc = reg.assess_risk(G, 1, "ana", risk_tier="LOW", assessment_path=_assessment(tmp_path, tier="HIGH"))
    assert lc["risk_tier"] == "LOW" and lc["risk_assessment_source"] is None


def _corrupt_json(tmp_path):
    p = tmp_path / "ruim.json"
    p.write_text("{x", encoding="utf-8")
    return p


@pytest.mark.parametrize("make,match", [
    (lambda t: t / "nao_existe.json", "não encontrada"),
    (lambda t: _assessment(t, model_version="v9-outro"), "versão"),
    (_corrupt_json, "ilegível"),
])
def test_risk_assessment_file_errors_are_typed(tmp_path, make, match):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    with pytest.raises(RiskAssessmentUnavailable, match=match):
        reg.assess_risk(G, 1, "ana", assessment_path=make(tmp_path))


def test_missing_tier_source_is_an_error_not_a_default(tmp_path):
    reg = _reg(tmp_path)
    reg.advance(G, 1, "RiskAssessment", "ana", WHY)
    with pytest.raises(RiskAssessmentUnavailable):
        reg.assess_risk(G, 1, "ana")
    assert reg.lifecycle(G, 1)["risk_tier"] is None


def test_assess_risk_only_in_risk_stage(tmp_path):
    with pytest.raises(InvalidTransition):
        _reg(tmp_path).assess_risk(G, 1, "ana", risk_tier="LOW")


def test_real_riskcredit_assessment_if_present():
    """Integração real: lê o risk_assessment.json do RiskCredit v3.1 quando o repo irmão existe."""
    policy = load_lifecycle_policy(ROOT / "configs" / "lifecycle_policy.yaml")
    p = (Path(policy["_base_dir"]) / policy["risk_assessment_path"]).resolve()
    if not p.exists():
        pytest.skip("RiskCredit governance/ não encontrado ao lado deste repo")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        reg = LocalModelRegistry(Path(d) / "r.json", policy=policy)
        reg.register(G, ARTIFACT_DIR)
        reg.advance(G, 1, "RiskAssessment", "ana", WHY)
        lc = reg.assess_risk(G, 1, "ana")
    assert lc["risk_tier"] == json.loads(p.read_text(encoding="utf-8"))["risk_tier"]
    assert lc["risk_assessment_source"]["model_version"] == "v3-20260929"
