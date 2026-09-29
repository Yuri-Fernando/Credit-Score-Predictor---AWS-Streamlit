"""Contrato de entrada e data quality gate (plano §5.6 e §5.7).

O schema vem de ``feature_schema.json`` publicado pelo RiskCredit. A
validação BLOQUEIA (em vez de preencher com zero, como a Lambda v1 fazia):
- campo ausente → erro; campo extra → erro (inclui atributos excluídos,
  como SEX/AGE, que não podem mais chegar ao modelo);
- tipo não numérico, NaN/inf → erro;
- valor fora da faixa válida → erro;
- PAY_x precisa ser inteiro em [-2, 9];
- corpo acima de ``MAX_BODY_BYTES`` ou lote acima de ``MAX_BATCH`` → erro.
Mensagens de erro nunca ecoam o valor recebido (evita vazar dado em log).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

MAX_BODY_BYTES = 16 * 1024
MAX_BATCH = 50


@dataclass
class ValidationResult:
    ok: bool
    records: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


class FeatureContract:
    def __init__(self, schema: dict):
        self.schema = schema
        self.fields = {f["name"]: f for f in schema["raw_input_features"]}
        self.model_features = schema["model_features_ordered"]
        self.excluded = set(schema.get("excluded_attributes", []))

    @classmethod
    def from_file(cls, path: str | Path) -> "FeatureContract":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def validate_record(self, rec: dict, idx: int = 0) -> list[dict]:
        errs = []
        if not isinstance(rec, dict):
            return [{"record": idx, "field": None, "error": "registro deve ser objeto JSON"}]
        for name in rec.keys() - self.fields.keys():
            code = "atributo_excluido_do_modelo" if name in self.excluded else "campo_nao_permitido"
            errs.append({"record": idx, "field": name, "error": code})
        for name, spec in self.fields.items():
            if name not in rec:
                errs.append({"record": idx, "field": name, "error": "campo_obrigatorio_ausente"})
                continue
            v = rec[name]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errs.append({"record": idx, "field": name, "error": "tipo_invalido"})
                continue
            if not math.isfinite(v):
                errs.append({"record": idx, "field": name, "error": "valor_nao_finito"})
                continue
            if not (spec["min"] <= v <= spec["max"]):
                errs.append({"record": idx, "field": name, "error": "fora_da_faixa_valida"})
            if name.startswith("PAY_") and not name.startswith("PAY_AMT") and float(v) != int(v):
                errs.append({"record": idx, "field": name, "error": "status_de_pagamento_deve_ser_inteiro"})
        return errs

    def validate_body(self, body: str | bytes) -> ValidationResult:
        raw = body.encode() if isinstance(body, str) else body
        if len(raw) > MAX_BODY_BYTES:
            return ValidationResult(False, errors=[{"error": "payload_muito_grande", "limit_bytes": MAX_BODY_BYTES}])
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return ValidationResult(False, errors=[{"error": "json_invalido"}])
        if not isinstance(payload, dict) or set(payload) - {"data", "records"} or not payload:
            return ValidationResult(False, errors=[{"error": "envelope_invalido", "expected": "{'data': {...}} ou {'records': [...]}"}])
        records = payload.get("records") if "records" in payload else [payload.get("data")]
        if not isinstance(records, list) or not records:
            return ValidationResult(False, errors=[{"error": "records_deve_ser_lista_nao_vazia"}])
        if len(records) > MAX_BATCH:
            return ValidationResult(False, errors=[{"error": "lote_muito_grande", "limit": MAX_BATCH}])
        errors = [e for i, r in enumerate(records) for e in self.validate_record(r, i)]
        return ValidationResult(not errors, records if not errors else [], errors)
