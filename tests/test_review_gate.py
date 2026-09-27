import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import review_gate as g  # noqa: E402

T = "baile-da-brota.arte_feed"
NOW = datetime(2026, 9, 26, 22, 0, tzinfo=timezone.utc)


def ledger_with(**task_fields):
    led = g.new_ledger()
    task = g.new_task()
    task.update(task_fields)
    led["tasks"][T] = task
    return led


class EvaluateTests(unittest.TestCase):
    def test_new_task_is_allowed_round_one(self):
        r = g.evaluate(g.new_ledger(), T, now=NOW)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["next_round"], 1)
        self.assertEqual(r["rounds_remaining"], 2)

    def test_two_rounds_then_blocked(self):
        r = g.evaluate(ledger_with(rounds_used=1), T, now=NOW)
        self.assertEqual((r["decision"], r["next_round"]), ("ALLOW", 2))
        r = g.evaluate(ledger_with(rounds_used=2), T, now=NOW)
        self.assertEqual((r["decision"], r["blocked_reason"]), ("BLOCKED", "rounds_exhausted"))

    def test_human_review_state_blocks_even_with_rounds_left(self):
        r = g.evaluate(ledger_with(rounds_used=0, state="HUMAN_REVIEW_REQUIRED", blocked_reason="transport_failures"), T, now=NOW)
        self.assertEqual((r["decision"], r["blocked_reason"]), ("BLOCKED", "transport_failures"))

    def test_three_transport_failures_block(self):
        r = g.evaluate(ledger_with(transport_failures=3), T, now=NOW)
        self.assertEqual((r["decision"], r["blocked_reason"]), ("BLOCKED", "transport_failures"))
        self.assertEqual(g.evaluate(ledger_with(transport_failures=2), T, now=NOW)["decision"], "ALLOW")

    def test_done_request_is_cached_and_does_not_consume(self):
        led = ledger_with(rounds_used=2, requests={"rq_aaaaaaaa": {"round": 2, "status": "done", "review_file": "data/reviews/x.json"}})
        r = g.evaluate(led, T, request_id="rq_aaaaaaaa", now=NOW)
        self.assertEqual(r["decision"], "CACHED")
        self.assertEqual(r["review_file"], "data/reviews/x.json")

    def test_in_flight_only_while_recent(self):
        recent = (NOW - timedelta(seconds=30)).isoformat()
        old = (NOW - timedelta(seconds=600)).isoformat()
        led = ledger_with(requests={"rq_bbbbbbbb": {"round": 1, "status": "reserved", "reserved_at": recent}})
        self.assertEqual(g.evaluate(led, T, request_id="rq_bbbbbbbb", now=NOW)["decision"], "IN_FLIGHT")
        led = ledger_with(requests={"rq_bbbbbbbb": {"round": 1, "status": "reserved", "reserved_at": old}})
        self.assertEqual(g.evaluate(led, T, request_id="rq_bbbbbbbb", now=NOW)["decision"], "ALLOW")

    def test_repeated_fingerprint_after_fix_blocks(self):
        led = ledger_with(rounds_used=1, fingerprints=["arte_feed:template_igual:9f2c"])
        blocked = g.evaluate(led, T, fingerprint="arte_feed:template_igual:9f2c", applied_fix=True, now=NOW)
        self.assertEqual((blocked["decision"], blocked["blocked_reason"]), ("BLOCKED", "repeated_fingerprint"))
        # sem correção aplicada, o mesmo erro NÃO bloqueia (pode ser só a primeira revisão repetida)
        self.assertEqual(g.evaluate(led, T, fingerprint="arte_feed:template_igual:9f2c", applied_fix=False, now=NOW)["decision"], "ALLOW")
        # erro diferente depois da correção segue permitido
        self.assertEqual(g.evaluate(led, T, fingerprint="arte_feed:outro:1111", applied_fix=True, now=NOW)["decision"], "ALLOW")

    def test_hourly_cap(self):
        led = g.new_ledger()
        led["global"] = {"window_start": (NOW - timedelta(minutes=10)).isoformat(), "count": 20}
        self.assertEqual(g.evaluate(led, T, now=NOW)["decision"], "RATE_LIMITED")
        led["global"] = {"window_start": (NOW - timedelta(minutes=61)).isoformat(), "count": 20}
        self.assertEqual(g.evaluate(led, T, now=NOW)["decision"], "ALLOW")


class ResetTests(unittest.TestCase):
    def test_reset_requires_author_and_reason_and_keeps_history(self):
        led = ledger_with(rounds_used=2, state="HUMAN_REVIEW_REQUIRED", blocked_reason="rounds_exhausted", fingerprints=["x"])
        with self.assertRaises(ValueError):
            g.apply_reset(led, T, "", "motivo", now=NOW)
        with self.assertRaises(ValueError):
            g.apply_reset(led, T, "filipe", "  ", now=NOW)
        with self.assertRaises(KeyError):
            g.apply_reset(led, "nao-existe.arte_feed", "filipe", "ok", now=NOW)
        g.apply_reset(led, T, "filipe", "corrigido o template", now=NOW)
        task = led["tasks"][T]
        self.assertEqual((task["rounds_used"], task["state"], task["fingerprints"]), (0, "OPEN", []))
        self.assertEqual(task["resets"][0]["by"], "filipe")
        self.assertEqual(task["resets"][0]["previous"]["rounds_used"], 2)
        self.assertEqual(g.evaluate(led, T, now=NOW)["decision"], "ALLOW")


class CliTests(unittest.TestCase):
    def run_cli(self, ledger_path, *args):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "review_gate.py"), "--ledger", ledger_path, *args],
            capture_output=True, text=True,
        )

    def test_exit_codes_and_reset_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ledger.json")
            g.save_ledger(ledger_with(rounds_used=2), path)
            r = self.run_cli(path, "check", "--task-id", T)
            self.assertEqual(r.returncode, 10)
            self.assertEqual(json.loads(r.stdout)["blocked_reason"], "rounds_exhausted")
            r = self.run_cli(path, "reset", "--task-id", T, "--by", "filipe", "--reason", "revisado")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.run_cli(path, "check", "--task-id", T).returncode, 0)
            self.assertEqual(self.run_cli(path, "reset", "--task-id", "nao-existe.x", "--by", "a", "--reason", "b").returncode, 2)

    def test_missing_ledger_file_means_allow(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(os.path.join(d, "nope.json"), "check", "--task-id", T)
            self.assertEqual(r.returncode, 0)

    def test_repo_ledger_is_valid_and_empty(self):
        led = g.load_ledger(os.path.join(ROOT, "data", "review-ledger.json"))
        self.assertEqual((led["max_review_rounds"], led["max_transport_failures"], led["tasks"]), (2, 3, {}))


if __name__ == "__main__":
    unittest.main()
