#!/usr/bin/env python3
"""Gate de revisão Claude: decide, ANTES de qualquer chamada, se uma tarefa ainda pode ser revisada.

Lê data/review-ledger.json (somente leitura, exceto `reset`, que exige autor e motivo).
O endpoint netlify/functions/claude-review.mjs é o único que grava rodadas no ledger e aplica
exatamente as mesmas regras; este script existe para o workflow nem montar o pedido quando a
tarefa já está bloqueada.

Códigos de saída de `check`:
  0  permitido       10 bloqueado (HUMAN_REVIEW_REQUIRED)
  11 já respondido (request_id em cache)   12 mesmo request_id em andamento
  13 limite por hora atingido
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_LEDGER = "data/review-ledger.json"
IN_FLIGHT_SECONDS = 120

EXIT = {"ALLOW": 0, "BLOCKED": 10, "CACHED": 11, "IN_FLIGHT": 12, "RATE_LIMITED": 13}


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def new_ledger():
    return {
        "version": 1,
        "max_review_rounds": 2,
        "max_transport_failures": 3,
        "hourly_cap": 20,
        "global": {"window_start": None, "count": 0},
        "tasks": {},
    }


def new_task():
    return {
        "rounds_used": 0,
        "transport_failures": 0,
        "state": "OPEN",
        "blocked_reason": None,
        "fingerprints": [],
        "requests": {},
        "resets": [],
        "updated_at": None,
    }


def load_ledger(path=DEFAULT_LEDGER):
    try:
        with open(path, encoding="utf-8") as f:
            ledger = json.load(f)
    except FileNotFoundError:
        return new_ledger()
    base = new_ledger()
    for key, value in base.items():
        ledger.setdefault(key, value)
    return ledger


def save_ledger(ledger, path=DEFAULT_LEDGER):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _hour_window_count(ledger, now):
    start = parse_iso(ledger.get("global", {}).get("window_start"))
    if start is None or now - start >= timedelta(hours=1):
        return 0
    return int(ledger["global"].get("count", 0))


def evaluate(ledger, task_id, request_id=None, fingerprint=None, applied_fix=False, now=None):
    """Decisão pura, sem efeitos colaterais. Mesmas regras do endpoint."""
    now = now or utcnow()
    max_rounds = int(ledger.get("max_review_rounds", 2))
    max_tf = int(ledger.get("max_transport_failures", 3))
    cap = int(ledger.get("hourly_cap", 20))
    task = ledger.get("tasks", {}).get(task_id) or new_task()
    used = int(task.get("rounds_used", 0))

    def out(decision, **extra):
        data = {
            "decision": decision,
            "task_id": task_id,
            "rounds_used": used,
            "rounds_remaining": max(0, max_rounds - used),
            "max_review_rounds": max_rounds,
        }
        data.update(extra)
        return data

    req = task.get("requests", {}).get(request_id) if request_id else None
    if req and req.get("status") == "done":
        return out("CACHED", review_file=req.get("review_file"))
    if req and req.get("status") == "reserved":
        reserved = parse_iso(req.get("reserved_at"))
        if reserved and (now - reserved).total_seconds() < IN_FLIGHT_SECONDS:
            return out("IN_FLIGHT")

    if task.get("state") == "HUMAN_REVIEW_REQUIRED":
        return out("BLOCKED", blocked_reason=task.get("blocked_reason") or "already_human_review")
    if used >= max_rounds:
        return out("BLOCKED", blocked_reason="rounds_exhausted")
    if int(task.get("transport_failures", 0)) >= max_tf:
        return out("BLOCKED", blocked_reason="transport_failures")
    if applied_fix and fingerprint and fingerprint in task.get("fingerprints", []):
        return out("BLOCKED", blocked_reason="repeated_fingerprint")
    if _hour_window_count(ledger, now) >= cap:
        return out("RATE_LIMITED")
    return out("ALLOW", next_round=used + 1)


def apply_reset(ledger, task_id, by, reason, now=None):
    if not by or not by.strip() or not reason or not reason.strip():
        raise ValueError("reset exige --by e --reason não vazios")
    now = now or utcnow()
    task = ledger.setdefault("tasks", {}).get(task_id)
    if task is None:
        raise KeyError(f"task_id desconhecido: {task_id}")
    task.setdefault("resets", []).append({
        "by": by.strip(),
        "reason": reason.strip(),
        "at": iso(now),
        "previous": {
            "rounds_used": task.get("rounds_used", 0),
            "transport_failures": task.get("transport_failures", 0),
            "state": task.get("state", "OPEN"),
        },
    })
    task["rounds_used"] = 0
    task["transport_failures"] = 0
    task["state"] = "OPEN"
    task["blocked_reason"] = None
    task["fingerprints"] = []
    task["updated_at"] = iso(now)
    return ledger


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ledger", default=DEFAULT_LEDGER)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="verifica se a tarefa pode ser revisada")
    c.add_argument("--task-id", required=True)
    c.add_argument("--request-id")
    c.add_argument("--fingerprint")
    c.add_argument("--applied-fix", action="store_true", help="uma correção foi aplicada desde a rodada anterior")

    s = sub.add_parser("status", help="mostra o registro da tarefa")
    s.add_argument("--task-id", required=True)

    r = sub.add_parser("reset", help="ação humana: zera as rodadas da tarefa (fica registrado)")
    r.add_argument("--task-id", required=True)
    r.add_argument("--by", required=True)
    r.add_argument("--reason", required=True)

    a = p.parse_args(argv)
    ledger = load_ledger(a.ledger)

    if a.cmd == "check":
        result = evaluate(ledger, a.task_id, a.request_id, a.fingerprint, a.applied_fix)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT[result["decision"]]
    if a.cmd == "status":
        print(json.dumps(ledger.get("tasks", {}).get(a.task_id) or new_task(), ensure_ascii=False, indent=2))
        return 0
    try:
        apply_reset(ledger, a.task_id, a.by, a.reason)
    except (ValueError, KeyError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    save_ledger(ledger, a.ledger)
    print(json.dumps({"ok": True, "task_id": a.task_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
