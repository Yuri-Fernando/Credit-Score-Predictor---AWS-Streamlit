"""Interpretador mínimo de Amazon States Language (ASL) — plano §5.1.

Executa localmente a definição de state machine em
``infra/terraform/templates/pipeline.asl.json.tftpl`` sem Step Functions e
sem AWS: cada ``Task`` é resolvida para uma função Python via
``resource_map`` (chave = valor literal do campo ``Resource`` no JSON, não
um ARN real). Suporta os tipos de estado usados pelo pipeline deste
projeto — ``Task``, ``Parallel``, ``Choice``, ``Succeed``, ``Fail`` — e
``Parameters``/``ResultPath``/``Catch`` (não implementa ``Retry``: retentativa
é responsabilidade do runtime real da AWS, não da lógica de negócio que este
interpretador valida).

Não é um substituto do Step Functions real — é suficiente para testar, sem
custo e sem rede, que a lógica de transição de estados do pipeline (quem vai
para onde, dado o resultado de cada Task) está correta.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

MAX_STEPS = 200  # guarda contra loop infinito em definição malformada


class AslError(RuntimeError):
    """Definição ASL malformada ou estado desconhecido referenciado em Next/Default/Catch."""


def _get_path(data: Any, path: str) -> Any:
    if path in ("$", ""):
        return data
    cur = data
    for part in path.lstrip("$").lstrip(".").split("."):
        if part:
            cur = cur[part]
    return cur


def _set_path(data: Any, path: str, value: Any) -> Any:
    if path in ("$", "", None):
        return value
    parts = [p for p in path.lstrip("$").lstrip(".").split(".") if p]
    cur = data
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value
    return data


def _resolve_parameters(params: dict, data: Any) -> dict:
    out = {}
    for k, v in params.items():
        if k.endswith(".$"):
            out[k[:-2]] = _get_path(data, v)
        else:
            out[k] = v
    return out


def _choice_matches(choice: dict, data: Any) -> bool:
    try:
        var = _get_path(data, choice["Variable"])
    except (KeyError, TypeError, IndexError):
        return False
    if "StringEquals" in choice:
        return var == choice["StringEquals"]
    if "BooleanEquals" in choice:
        return var == choice["BooleanEquals"]
    if "NumericEquals" in choice:
        return var == choice["NumericEquals"]
    return False


_TERMINAL_TYPES = {"Succeed", "Fail"}
_VALID_TYPES = {"Task", "Parallel", "Choice", "Pass", "Succeed", "Fail"}


def validate_structure(definition: dict) -> list[str]:
    """Validação estrutural real da definição ASL (sem depender do serviço da AWS).

    Confere: ``StartAt`` existe, todo ``Type`` é conhecido, todo estado não
    terminal tem ``Next`` ou ``End``, toda referência (``Next``/``Default``/
    ``Catch[].Next``/``Choices[].Next``) aponta para um estado existente no
    mesmo escopo (top-level ou dentro de cada branch do Parallel), Task tem
    ``Resource``, Choice tem ``Choices`` não vazio e ``Default``, Parallel tem
    ``Branches`` não vazio (cada branch validada recursivamente). Retorna a
    lista de problemas encontrados — vazia significa definição válida.
    """
    problems: list[str] = []

    def check_states(states: dict, scope: str) -> None:
        for name, state in states.items():
            stype = state.get("Type")
            where = f"{scope}.{name}"
            if stype not in _VALID_TYPES:
                problems.append(f"{where}: Type desconhecido/ausente ({stype!r})")
                continue
            if stype == "Task" and "Resource" not in state:
                problems.append(f"{where}: Task sem Resource")
            if stype == "Choice":
                choices = state.get("Choices")
                if not choices:
                    problems.append(f"{where}: Choice sem Choices")
                else:
                    for i, c in enumerate(choices):
                        if c.get("Next") not in states:
                            problems.append(f"{where}.Choices[{i}]: Next {c.get('Next')!r} não existe em {scope}")
                if "Default" not in state:
                    problems.append(f"{where}: Choice sem Default")
                elif state["Default"] not in states:
                    problems.append(f"{where}: Default {state['Default']!r} não existe em {scope}")
            if stype == "Parallel":
                branches = state.get("Branches")
                if not branches:
                    problems.append(f"{where}: Parallel sem Branches")
                else:
                    for i, branch in enumerate(branches):
                        if "StartAt" not in branch or branch["StartAt"] not in branch.get("States", {}):
                            problems.append(f"{where}.Branches[{i}]: StartAt ausente/inválido")
                        else:
                            check_states(branch["States"], f"{where}.Branches[{i}]")
            for catch in state.get("Catch", []):
                if catch.get("Next") not in states:
                    problems.append(f"{where}.Catch: Next {catch.get('Next')!r} não existe em {scope}")
            if stype not in _TERMINAL_TYPES and stype != "Choice":
                has_next, has_end = "Next" in state, state.get("End") is True
                if not has_next and not has_end:
                    problems.append(f"{where}: sem Next e sem End=true")
                if has_next and state["Next"] not in states:
                    problems.append(f"{where}: Next {state['Next']!r} não existe em {scope}")

    if "StartAt" not in definition:
        problems.append("definição sem StartAt")
    elif "States" not in definition or definition["StartAt"] not in definition["States"]:
        problems.append(f"StartAt {definition.get('StartAt')!r} não existe em States")
    if "States" not in definition or not definition["States"]:
        problems.append("definição sem States")
    else:
        check_states(definition["States"], "States")
    return problems


def run(definition: dict, input_: dict, resource_map: dict[str, Callable[[Any], Any]]) -> dict:
    """Executa a state machine a partir de ``StartAt`` até um estado terminal.

    Retorna ``{"status": "SUCCEEDED"|"FAILED", "output": ..., "path": [...]}``.
    ``path`` é a sequência de nomes de estado visitados — útil para afirmar,
    nos testes, que o pipeline tomou a bifurcação esperada.
    """
    states = definition["States"]
    state_name = definition["StartAt"]
    data: Any = copy.deepcopy(input_)
    path: list[str] = []
    for _ in range(MAX_STEPS):
        if state_name not in states:
            raise AslError(f"estado referenciado e inexistente: {state_name!r}")
        path.append(state_name)
        state = states[state_name]
        stype = state["Type"]

        if stype == "Succeed":
            return {"status": "SUCCEEDED", "output": data, "path": path}
        if stype == "Fail":
            return {"status": "FAILED", "output": data, "error": state.get("Error"),
                     "cause": state.get("Cause"), "path": path}
        if stype == "Choice":
            nxt = next((c["Next"] for c in state["Choices"] if _choice_matches(c, data)), state.get("Default"))
            if nxt is None:
                raise AslError(f"Choice {state_name!r} sem ramo correspondente e sem Default")
            state_name = nxt
            continue

        try:
            if stype == "Task":
                fn = resource_map[state["Resource"]]
                call_input = _resolve_parameters(state["Parameters"], data) if "Parameters" in state else data
                result = fn(call_input)
                data = _set_path(data, state.get("ResultPath", "$"), result)
            elif stype == "Parallel":
                results = [run(branch, data, resource_map) for branch in state["Branches"]]
                failed = next((r for r in results if r["status"] == "FAILED"), None)
                if failed is not None:
                    raise AslError(f"branch do Parallel {state_name!r} falhou: {failed.get('error')}")
                data = _set_path(data, state.get("ResultPath", "$"), [r["output"] for r in results])
            elif stype == "Pass":
                if "Parameters" in state:
                    data = _set_path(data, state.get("ResultPath", "$"), _resolve_parameters(state["Parameters"], data))
            else:
                raise AslError(f"tipo de estado não suportado pelo interpretador local: {stype!r}")
        except AslError:
            raise
        except Exception as exc:  # noqa: BLE001 — Catch genérico, igual ao States.ALL do ASL real
            catches = state.get("Catch", [])
            if not catches:
                raise
            data = _set_path(data, catches[0].get("ResultPath", "$.error"),
                              {"error": type(exc).__name__, "message": str(exc)})
            state_name = catches[0]["Next"]
            continue

        if "Next" in state:
            state_name = state["Next"]
        elif state.get("End"):
            return {"status": "SUCCEEDED", "output": data, "path": path}
        else:
            raise AslError(f"estado {state_name!r} sem Next/End")
    raise AslError(f"execução excedeu {MAX_STEPS} transições — possível ciclo na definição")
