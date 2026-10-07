"""Testes do pipeline de orquestração (plano §5.1 — Step Functions), sem AWS.

Dois níveis:
1. Sintaxe/estrutura real da definição ASL em
   ``infra/terraform/templates/pipeline.asl.json.tftpl`` — o mesmo arquivo que
   o Terraform renderiza com ``templatefile()`` para a state machine real
   (`infra/terraform/stepfunctions.tf`, validado com `terraform validate`,
   nunca aplicado).
2. Simulação local da lógica de transição de estados (``src/mlops/asl_runner``)
   usando os steps reais (``src/mlops/pipeline_steps``) sobre os artefatos
   reais do projeto (golden samples, registry aprovado) — sem chamar a AWS.

Nota honesta sobre o teste "ponta a ponta": o monitoramento de drift
(``src/mlops/monitoring.py``) compara o PSI do **score** contra o perfil de
referência do RiskCredit. Como documentado no próprio ``README.md``
(seção "Resultados") e reproduzido abaixo, **qualquer lote sintético**
disponível neste repositório — golden samples (casos de borda, não uma
amostra aleatória da população) ou amostragem independente por feature do
perfil de referência — fica "vermelho" no PSI do score (estrutura conjunta
diferente da do treino). Isso não é um bug do teste: é a limitação real e
documentada do monitoramento offline sem tráfego de produção real. Por
isso o teste ponta-a-ponta do "caminho feliz" (`test_pipeline_...`) afirma
o resultado **real e honesto** (halt em ``HoldForDriftReview``), e os 4
ramos da decisão (rollback / hold-por-drift / hold-por-canary / promote)
são testados isoladamente a partir do estado ``CheckCanaryAndDrift``,
semeando ``decision``/``drift_red`` diretamente — isso ainda é simulação
real de transição de estado (mesma definição ASL, mesmo interpretador),
só sem depender de conseguir fabricar um lote estatisticamente "limpo".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mlops import asl_runner, pipeline_steps  # noqa: E402

TEMPLATE_PATH = ROOT / "infra" / "terraform" / "templates" / "pipeline.asl.json.tftpl"
GOLDEN = json.loads((pipeline_steps.CHAMPION_DIR / "golden_samples.json").read_text(encoding="utf-8"))

_DUMMY_ARNS = {
    "${validate_lambda_arn}": "arn:aws:lambda:sa-east-1:000000000000:function:credit-score-staging-pipeline-validate",
    "${score_lambda_arn}": "arn:aws:lambda:sa-east-1:000000000000:function:credit-score-staging-pipeline-score",
    "${combine_lambda_arn}": "arn:aws:lambda:sa-east-1:000000000000:function:credit-score-staging-pipeline-combine",
    "${monitor_lambda_arn}": "arn:aws:lambda:sa-east-1:000000000000:function:credit-score-staging-pipeline-monitor",
    "${publish_lambda_arn}": "arn:aws:lambda:sa-east-1:000000000000:function:credit-score-staging-pipeline-publish",
}


def _render_definition() -> dict:
    """Mesma substituição que o `templatefile()` do Terraform faz — aqui com ARNs fictícios,
    só para validar sintaxe/estrutura e simular transições, sem nenhuma chamada à AWS."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder, value in _DUMMY_ARNS.items():
        text = text.replace(placeholder, value)
    assert "${" not in text, "placeholder não substituído sobrou no template"
    return json.loads(text)


RESOURCE_MAP = {
    _DUMMY_ARNS["${validate_lambda_arn}"]: pipeline_steps.validate_batch,
    _DUMMY_ARNS["${score_lambda_arn}"]: pipeline_steps.score_batch,
    _DUMMY_ARNS["${combine_lambda_arn}"]: pipeline_steps.combine_shadow,
    _DUMMY_ARNS["${monitor_lambda_arn}"]: pipeline_steps.monitor_drift,
    _DUMMY_ARNS["${publish_lambda_arn}"]: pipeline_steps.publish_manifest,
}

_CHOICE_SUBSET = ("CheckCanaryAndDrift", "RollbackChallenger", "HoldForDriftReview",
                  "HoldPendingReview", "PublishManifest", "Published", "RejectBatch")


def _choice_only_definition(definition: dict) -> dict:
    """Sub-definição começando direto no Choice — isola a lógica de roteamento
    (rollback / hold-drift / hold-canary / promote) de qualquer scoring real."""
    return {"StartAt": "CheckCanaryAndDrift",
            "States": {k: v for k, v in definition["States"].items() if k in _CHOICE_SUBSET}}


# --------------------------------------------------------------------------- sintaxe/estrutura real do ASL

def test_asl_template_is_well_formed_json_after_substitution():
    """O arquivo que o Terraform usa em `templatefile()` precisa ser JSON válido
    assim que os placeholders `${...}` são substituídos por ARNs."""
    raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    placeholders = set(re.findall(r"\$\{[a-z_]+\}", raw))
    assert placeholders == set(_DUMMY_ARNS), "placeholders do template e do teste saíram de sincronia"
    definition = _render_definition()
    assert definition["StartAt"] == "ValidateBatch"


def test_asl_structure_has_no_dangling_references():
    problems = asl_runner.validate_structure(_render_definition())
    assert problems == []


def test_asl_structure_catches_broken_definition():
    broken = {"StartAt": "A", "States": {"A": {"Type": "Task", "Resource": "x", "Next": "Inexistente"}}}
    problems = asl_runner.validate_structure(broken)
    assert any("Inexistente" in p for p in problems)


def test_asl_structure_requires_choice_default_and_parallel_branches():
    broken = {"StartAt": "C", "States": {
        "C": {"Type": "Choice", "Choices": [{"Variable": "$.x", "StringEquals": "a", "Next": "C"}]},
    }}
    problems = asl_runner.validate_structure(broken)
    assert any("Default" in p for p in problems)


# --------------------------------------------------------------------------- simulação ponta-a-ponta (dados reais)

def test_pipeline_end_to_end_validate_score_shadow_halts_on_drift():
    """Caminho real completo — ValidateBatch → ScoreShadow (Parallel) → CombineShadow →
    MonitorDrift → Choice — sobre golden samples reais, sem challenger publicado
    (fallback = champion, concordância 100%) e sem nenhuma chamada à AWS.

    Resultado honesto: o canary promoveria (champion == challenger), mas o gate de
    drift do score (ver nota do módulo) corretamente SUSPENDE a publicação — o
    pipeline não publica manifesto quando o monitoramento não confia no lote."""
    assert not pipeline_steps.CHALLENGER_DIR.exists(), "fixture assume que não há challenger publicado"
    definition = _render_definition()
    records = [g["input"] for g in GOLDEN[:10]]
    result = asl_runner.run(definition, {"records": records}, RESOURCE_MAP)
    assert result["path"][:4] == ["ValidateBatch", "ScoreShadow", "CombineShadow", "MonitorDrift"]
    assert result["output"]["decision"]["action"] == "promote_next_step"
    assert result["output"]["decision"]["checks"]["score_psi"] is True  # champion==challenger: PSI do shadow é 0
    assert result["output"]["drift_red"] is True  # ver nota do módulo: limitação real e documentada
    assert result["status"] == "SUCCEEDED"
    assert result["path"][-1] == "HoldForDriftReview"


def test_pipeline_rejects_batch_with_contract_violation():
    """SEX (atributo excluído) no payload → ValidateBatch levanta PipelineError →
    Catch → RejectBatch (estado Fail), sem chegar a nenhuma etapa de score/publish."""
    bad_record = {**GOLDEN[0]["input"], "SEX": 2}
    definition = _render_definition()
    result = asl_runner.run(definition, {"records": [bad_record]}, RESOURCE_MAP)
    assert result["status"] == "FAILED"
    assert result["path"] == ["ValidateBatch", "RejectBatch"]
    assert result["error"] == "PipelineRejected"
    assert "errors" in json.loads(result["output"]["error"]["message"])


def test_pipeline_rejects_empty_batch():
    definition = _render_definition()
    result = asl_runner.run(definition, {"records": []}, RESOURCE_MAP)
    assert result["status"] == "FAILED"
    assert result["path"] == ["ValidateBatch", "RejectBatch"]


# --------------------------------------------------------------------------- os 4 ramos do Choice (isolados)

def test_choice_routes_to_rollback():
    sub = _choice_only_definition(_render_definition())
    seed = {"decision": {"action": "rollback"}, "drift_red": False}
    result = asl_runner.run(sub, seed, RESOURCE_MAP)
    assert result["status"] == "FAILED"
    assert result["path"] == ["CheckCanaryAndDrift", "RollbackChallenger"]
    assert result["error"] == "CanaryRollback"


def test_choice_routes_to_hold_for_drift_even_when_canary_would_promote():
    """drift_red tem prioridade sobre um canary que promoveria — defesa em profundidade."""
    sub = _choice_only_definition(_render_definition())
    seed = {"decision": {"action": "promote_next_step"}, "drift_red": True}
    result = asl_runner.run(sub, seed, RESOURCE_MAP)
    assert result["status"] == "SUCCEEDED"
    assert result["path"] == ["CheckCanaryAndDrift", "HoldForDriftReview"]


def test_choice_routes_to_hold_pending_review():
    sub = _choice_only_definition(_render_definition())
    seed = {"decision": {"action": "hold"}, "drift_red": False}
    result = asl_runner.run(sub, seed, RESOURCE_MAP)
    assert result["status"] == "SUCCEEDED"
    assert result["path"] == ["CheckCanaryAndDrift", "HoldPendingReview"]


def test_choice_routes_to_publish_manifest_and_generates_real_manifest():
    """Único ramo que chega à Task real `publish_manifest` — usa o registry real do
    projeto (``registry/model_registry.json``, já com a v1 Approved), sem mutá-lo."""
    sub = _choice_only_definition(_render_definition())
    seed = {"decision": {"action": "promote_next_step"}, "drift_red": False,
            "model_package_group": "riskcredit-pd-12m"}
    result = asl_runner.run(sub, seed, RESOURCE_MAP)
    assert result["status"] == "SUCCEEDED"
    assert result["path"] == ["CheckCanaryAndDrift", "PublishManifest", "Published"]
    manifest = result["output"]["manifest"]
    assert manifest["applied"] is False
    assert manifest["model_package_version"] >= 1
    assert manifest["model_package_group"] == "riskcredit-pd-12m"


def test_choice_publish_fails_without_approved_version_and_is_caught():
    """Sem versão aprovada para o grupo → PipelineError na Task → Catch → RejectBatch."""
    sub = _choice_only_definition(_render_definition())
    seed = {"decision": {"action": "promote_next_step"}, "drift_red": False,
            "model_package_group": "grupo-sem-versao-aprovada"}
    result = asl_runner.run(sub, seed, RESOURCE_MAP)
    assert result["status"] == "FAILED"
    assert result["path"] == ["CheckCanaryAndDrift", "PublishManifest", "RejectBatch"]


# --------------------------------------------------------------------------- unidade: pipeline_steps.publish_manifest

def test_publish_manifest_fails_without_approved_version(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_steps, "REGISTRY_PATH", tmp_path / "empty_registry.json")
    with pytest.raises(pipeline_steps.PipelineError):
        pipeline_steps.publish_manifest({"model_package_group": "grupo-sem-versao"})
