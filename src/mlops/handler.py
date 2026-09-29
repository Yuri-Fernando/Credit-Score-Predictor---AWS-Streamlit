"""Handler de inferência v3 (Lambda) — endurecido, testável localmente, NÃO implantado.

Diferenças para ``Nuvem/lambda_function.py`` (v1, em produção):
- valida contra o contrato do RiskCredit e **rejeita** (422) em vez de
  preencher campos ausentes com 0;
- limite de tamanho (413), JSON inválido (400), envelope inválido (400);
- identidade/autorização ficam no API Gateway (JWT/Cognito — ROADMAP), não no corpo;
- log estruturado JSON por requisição (request_id, model_version, status,
  latência) **sem** valores de entrada;
- persiste features do modelo + PD + versão (para monitoramento de drift),
  não o payload bruto;
- clientes boto3 criados sob demanda: ``INFERENCE_MODE=local`` roda o
  XGBoost local e ``PERSIST=false`` desliga o DynamoDB → testes sem AWS.
Variáveis: INFERENCE_MODE (local|sagemaker), SAGEMAKER_ENDPOINT, DYNAMODB_TABLE, PERSIST.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from decimal import Decimal
from functools import lru_cache

from src.mlops.contract import FeatureContract
from src.mlops.scoring import ARTIFACT_DIR, LocalScorer, risk_band

logger = logging.getLogger("credit-score-v3")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

LOG_SINK: list[dict] = []  # espelho em memória para testes/monitoramento local


@lru_cache(maxsize=1)
def _contract() -> FeatureContract:
    return FeatureContract.from_file(ARTIFACT_DIR / "feature_schema.json")


@lru_cache(maxsize=1)
def _scorer() -> LocalScorer:
    return LocalScorer(ARTIFACT_DIR)


def _respond(code: int, body: dict, request_id: str, t0: float, model_version: str, n: int = 0) -> dict:
    rec = {"event": "inference", "request_id": request_id, "status_code": code, "model_version": model_version,
           "n_records": n, "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    LOG_SINK.append(rec)
    logger.info(json.dumps(rec))
    return {"statusCode": code, "headers": {"Content-Type": "application/json", "X-Request-Id": request_id},
            "body": json.dumps({**body, "request_id": request_id}, ensure_ascii=False)}


def _sagemaker_predict(features_rows: list[list[float]]) -> list[float]:
    import boto3  # sob demanda
    rt = boto3.client("sagemaker-runtime")
    csv = "\n".join(",".join(repr(float(v)) for v in row) for row in features_rows)
    resp = rt.invoke_endpoint(EndpointName=os.environ["SAGEMAKER_ENDPOINT"], ContentType="text/csv", Body=csv)
    return [float(x) for x in resp["Body"].read().decode().replace("\n", ",").split(",") if x.strip()]


def _persist(request_id: str, model_version: str, frame, pds) -> None:
    import boto3
    table = boto3.resource("dynamodb").Table(os.environ["DYNAMODB_TABLE"])
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with table.batch_writer() as bw:
        for i, (row, p) in enumerate(zip(frame.to_dict(orient="records"), pds)):
            bw.put_item(Item={"request_id": f"{request_id}#{i}", "timestamp": ts, "model_version": model_version,
                              "pd": Decimal(str(round(float(p), 6))),
                              "features": {k: Decimal(str(round(float(v), 6))) for k, v in row.items()}})


def lambda_handler(event, context=None):
    t0 = time.perf_counter()
    request_id = getattr(context, "aws_request_id", None) or str(uuid.uuid4())
    scorer = _scorer()
    version = scorer.model_version
    body = event.get("body") if isinstance(event, dict) and "body" in event else json.dumps(event)
    if isinstance(event, dict) and event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body)
    if body is None:
        return _respond(400, {"error": "corpo_ausente"}, request_id, t0, version)
    v = _contract().validate_body(body)
    if not v.ok:
        err = v.errors[0].get("error")
        code = 413 if err == "payload_muito_grande" else 400 if err in (
            "json_invalido", "envelope_invalido", "records_deve_ser_lista_nao_vazia", "lote_muito_grande") else 422
        return _respond(code, {"error": "validacao", "details": v.errors[:20]}, request_id, t0, version)
    try:
        frame = scorer.model_frame(v.records)
        if os.environ.get("INFERENCE_MODE", "local") == "sagemaker":
            pds = _sagemaker_predict(frame.to_numpy().tolist())
        else:
            pds = scorer.predict_pd(v.records).tolist()
        if os.environ.get("PERSIST", "false").lower() == "true":
            _persist(request_id, version, frame, pds)
    except Exception as exc:  # erro interno sem detalhe de dado
        logger.error(json.dumps({"event": "inference_error", "request_id": request_id, "error": type(exc).__name__}))
        return _respond(500, {"error": "erro_interno"}, request_id, t0, version, len(v.records))
    results = [{"pd": round(float(p), 6), "risk_band": risk_band(float(p))} for p in pds]
    return _respond(200, {"model_version": version, "results": results,
                          "note": "score para simulação; não constitui decisão de crédito"},
                    request_id, t0, version, len(results))
