#!/usr/bin/env python3
"""Envia um pedido de revisão ao endpoint claude-review e grava a resposta.

Não publica nada e não altera produção: só pede o parecer. Antes de chamar, consulta o gate local
(data/review-ledger.json); tarefa bloqueada => não chama o endpoint (HUMAN_REVIEW_REQUIRED).

Variáveis de ambiente (segredos do GitHub Actions; nunca impressas):
  CLAUDE_REVIEW_URL, CLAUDE_REVIEW_KEY, CLAUDE_REVIEW_HMAC_SECRET

Códigos de saída:
  0  parecer recebido (REVIEWED ou CACHED)     10 HUMAN_REVIEW_REQUIRED (bloqueado ou escalado)
  13 limite por hora                            20 assinatura/chave recusada (401)
  21 pedido inválido (400)                      22 outro erro HTTP     23 sem resposta (rede/timeout)
  30 UNAVAILABLE (Claude indisponível; a rodada não foi consumida)
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_gate  # noqa: E402


def sign(secret, timestamp, raw_body):
    """HMAC-SHA256 de "<timestamp>.<corpo>", igual ao endpoint (netlify/functions/lib/review-core.mjs)."""
    return hmac.new(secret.encode("utf-8"), f"{timestamp}.{raw_body}".encode("utf-8"), hashlib.sha256).hexdigest()


def blocked_response(req, ev):
    return {
        "schema_version": "1.0",
        "request_id": req["request_id"],
        "task_id": req["task_id"],
        "round": ev["rounds_used"],
        "decision": "HUMAN_REVIEW_REQUIRED",
        "blocked_reason": ev.get("blocked_reason", "already_human_review"),
        "claude_called": False,
        "advisory_only": True,
        "rounds_used": ev["rounds_used"],
        "rounds_remaining": ev["rounds_remaining"],
        "next_action": "HUMAN_REVIEW_REQUIRED",
    }


def post(url, key, secret, raw_body, timeout):
    ts = str(int(time.time()))
    request = urllib.request.Request(
        url,
        data=raw_body.encode("utf-8"),
        method="POST",
        headers={
            "content-type": "application/json",
            "x-review-key": key,
            "x-review-timestamp": ts,
            "x-review-signature": sign(secret, ts, raw_body),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--request-file", required=True)
    p.add_argument("--output-json", required=True)
    p.add_argument("--ledger", default=review_gate.DEFAULT_LEDGER)
    p.add_argument("--queue", default="data/publish-queue.json")
    p.add_argument("--update-queue", action="store_true", help="grava o resultado no item da fila (data/publish-queue.json)")
    a = p.parse_args(argv)

    with open(a.request_file, encoding="utf-8") as f:
        req = json.load(f)

    ledger = review_gate.load_ledger(a.ledger)
    ev = review_gate.evaluate(
        ledger, req["task_id"], req.get("request_id"),
        (req.get("context") or {}).get("error_fingerprint"), bool((req.get("context") or {}).get("applied_fix")),
    )
    result, code = None, None
    if ev["decision"] == "BLOCKED":
        result, code = blocked_response(req, ev), 10
    elif ev["decision"] == "RATE_LIMITED":
        print("Limite de revisões por hora atingido; não chamei o endpoint.", file=sys.stderr)
        return 13

    if result is None:
        url = os.environ.get("CLAUDE_REVIEW_URL", "")
        key = os.environ.get("CLAUDE_REVIEW_KEY", "")
        secret = os.environ.get("CLAUDE_REVIEW_HMAC_SECRET", "")
        missing = [n for n, v in (("CLAUDE_REVIEW_URL", url), ("CLAUDE_REVIEW_KEY", key), ("CLAUDE_REVIEW_HMAC_SECRET", secret)) if not v]
        if missing:
            print("Configuração ausente: " + ", ".join(missing), file=sys.stderr)
            return 22
        raw = json.dumps(req, ensure_ascii=False, separators=(",", ":"))
        timeout = int(req.get("deadline_s") or 25) + 10
        try:
            _, result = post(url, key, secret, raw, timeout)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            print(f"Endpoint respondeu HTTP {e.code}: {detail}", file=sys.stderr)
            return {401: 20, 400: 21, 429: 13}.get(e.code, 22)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"Sem resposta do endpoint: {type(e).__name__}", file=sys.stderr)
            return 23
        decision = result.get("decision")
        code = {"REVIEWED": 0, "CACHED": 0, "HUMAN_REVIEW_REQUIRED": 10, "UNAVAILABLE": 30}.get(decision, 22)

    os.makedirs(os.path.dirname(a.output_json) or ".", exist_ok=True)
    with open(a.output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")

    news_id = req.get("news_id")
    if a.update_queue and news_id:
        import subprocess
        subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_publish_queue.py"),
             "--queue", a.queue, "--id", news_id, "--review-json", a.output_json],
            check=True,
        )
    print(json.dumps({"decision": result.get("decision"), "next_action": result.get("next_action"), "task_id": result.get("task_id"), "round": result.get("round")}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
