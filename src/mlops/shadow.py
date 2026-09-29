"""Shadow deployment e política de canary (plano §5.4) — avaliação offline.

Shadow: o challenger recebe as mesmas requisições que o champion, mas sua
resposta não é devolvida ao cliente; compara-se distribuição de score (PSI),
correlação de ranking, concordância de decisão no limiar, latência e erros.
Canary: dado um resultado de shadow e métricas de canário, aplica os gates de
``configs/canary_policy.yaml`` e decide promover / manter / rollback. O
roteamento real de tráfego (variantes do endpoint SageMaker) está no ROADMAP.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
from scipy.stats import spearmanr

from src.mlops.monitoring import psi_against_reference


def _timed(fn: Callable, records: list[dict]) -> tuple[np.ndarray, list[float]]:
    lat, out = [], []
    for r in records:
        t0 = time.perf_counter()
        out.append(float(np.asarray(fn([r])).ravel()[0]))
        lat.append((time.perf_counter() - t0) * 1000)
    return np.array(out), lat


def shadow_compare(champion: Callable, challenger: Callable, records: list[dict], threshold: float) -> dict:
    pc, lc = _timed(champion, records)
    ps, ls = _timed(challenger, records)
    edges = np.unique(np.quantile(pc, np.linspace(0, 1, 11))[1:-1])
    ref = {"type": "continuous", "edges": edges.tolist(),
           "proportions": (np.bincount(np.searchsorted(edges, pc, side="right"), minlength=len(edges) + 1)
                           / len(pc)).tolist()}
    agree = float(((pc < threshold) == (ps < threshold)).mean())
    return {"n": len(records), "score_psi_challenger_vs_champion": psi_against_reference(ref, ps),
            "spearman_rank_corr": float(spearmanr(pc, ps).statistic), "decision_agreement": agree,
            "approval_rate_champion": float((pc < threshold).mean()),
            "approval_rate_challenger": float((ps < threshold).mean()),
            "p95_latency_ms_champion": float(np.percentile(lc, 95)),
            "p95_latency_ms_challenger": float(np.percentile(ls, 95)), "threshold": threshold}


def canary_decision(shadow: dict, canary_ops: dict, policy: dict) -> dict:
    g = policy["gates"]
    checks = {
        "error_rate": canary_ops["error_rate"] <= g["max_error_rate"],
        "p95_latency": canary_ops["p95_latency_ms"] <= g["max_p95_latency_ms"],
        "score_psi": shadow["score_psi_challenger_vs_champion"] <= g["max_score_psi"],
        "decision_agreement": shadow["decision_agreement"] >= g["min_decision_agreement"],
        "rank_corr": shadow["spearman_rank_corr"] >= g["min_rank_corr"],
    }
    failed = [k for k, ok in checks.items() if not ok]
    hard = [k for k in failed if k in policy["rollback_on"]]
    action = "rollback" if hard else ("hold" if failed else "promote_next_step")
    return {"checks": checks, "failed": failed, "action": action, "steps": policy["traffic_steps"]}
