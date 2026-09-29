"""Monitoramento do serviço de inferência (plano §5.5) — offline, sem CloudWatch.

Entrada: lote de registros de inferência (features do modelo + score), como os
gravados no DynamoDB/data capture. Referência: ``reference_profile.json``
publicado pelo RiskCredit (distribuições de treino).
Saídas: PSI por feature e do score, taxa de violação de schema, taxa de
missing, drift de calibração/performance quando o alvo amadurecer, alertas.
Métricas operacionais (invocações, erro, p95, throttles) seriam CloudWatch —
aqui calculadas a partir do log estruturado do handler (``operational_metrics``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GREEN, AMBER = 0.10, 0.25


def _level(v: float) -> str:
    return "green" if v < GREEN else "amber" if v < AMBER else "red"


def psi_against_reference(spec: dict, x: np.ndarray, eps: float = 1e-4) -> float:
    x = np.asarray(x, dtype=float)
    ref = np.clip(np.asarray(spec["proportions"], dtype=float), eps, None)
    if spec["type"] == "discrete":
        vals = np.asarray(spec["values"])
        cur = np.array([(x == v).mean() for v in vals])
        other = 1 - cur.sum()  # valor nunca visto no treino também é drift
        cur, ref = np.append(cur, other), np.append(ref, eps)
    else:
        idx = np.searchsorted(np.asarray(spec["edges"]), x, side="right")
        cur = np.bincount(idx, minlength=len(ref)) / len(x)
    cur = np.clip(cur, eps, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def drift_report(reference: dict, batch: pd.DataFrame, score_col: str = "pd") -> pd.DataFrame:
    rows = []
    for f, spec in reference["features"].items():
        col = score_col if f == "__score__" else f
        if col not in batch:
            continue
        v = psi_against_reference(spec, batch[col].to_numpy())
        rows.append({"feature": "score" if f == "__score__" else f, "psi": v, "alert": _level(v)})
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)


def sample_from_reference(reference: dict, features: list[str], n: int, seed: int = 0) -> pd.DataFrame:
    """Gera um lote 'estável' a partir do perfil de referência (controle negativo:
    PSI esperado ≈ 0). Dentro de cada bin contínuo, amostra uniforme entre bordas."""
    rng = np.random.default_rng(seed)
    out = {}
    for f in features:
        spec = reference["features"][f]
        p = np.asarray(spec["proportions"]) / np.sum(spec["proportions"])
        if spec["type"] == "discrete":
            out[f] = rng.choice(spec["values"], size=n, p=p)
        else:
            e = np.asarray(spec["edges"])
            lo = np.concatenate([[e[0] - (e[1] - e[0] if len(e) > 1 else 1)], e])
            hi = np.concatenate([e, [e[-1] + (e[-1] - e[-2] if len(e) > 1 else 1)]])
            b = rng.choice(len(p), size=n, p=p)
            out[f] = rng.uniform(lo[b], hi[b])
    return pd.DataFrame(out)


def operational_metrics(log_records: list[dict]) -> dict:
    """Métricas RED a partir do log estruturado do handler."""
    df = pd.DataFrame(log_records)
    lat = df["latency_ms"].to_numpy(float)
    return {"invocations": int(len(df)),
            "error_rate": float((df["status_code"] >= 500).mean()),
            "client_error_rate": float(df["status_code"].between(400, 499).mean()),
            "schema_violation_rate": float((df["status_code"] == 422).mean()),
            "p50_latency_ms": float(np.percentile(lat, 50)), "p95_latency_ms": float(np.percentile(lat, 95))}


def performance_when_labeled(y: np.ndarray, p: np.ndarray) -> dict:
    from sklearn.metrics import roc_auc_score
    return {"n": int(len(y)), "auc": float(roc_auc_score(y, p)), "gini": float(2 * roc_auc_score(y, p) - 1),
            "calibration_gap_pp": float((np.mean(p) - np.mean(y)) * 100)}
