import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import request_claude_review as rc  # noqa: E402
import review_gate as g  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "request_claude_review.py")
REQ = {
    "schema_version": "1.0", "request_id": "rq_py_0001", "task_id": "n1.arte_feed", "news_id": "n1", "round": 1,
    "trigger": "segunda_opiniao", "stage": "arte_feed", "requested_by": "workflow", "context": {},
}


class FakeEndpoint(http.server.BaseHTTPRequestHandler):
    seen = []
    reply = {"schema_version": "1.0", "request_id": "rq_py_0001", "task_id": "n1.arte_feed", "round": 1, "decision": "REVIEWED",
             "claude_called": True, "advisory_only": True, "rounds_used": 1, "rounds_remaining": 1, "next_action": "PUBLISH_IF_VALIDATOR_PASSES",
             "review": {"status": "OK", "publish": "SIM"}}

    def do_POST(self):
        body = self.rfile.read(int(self.headers["content-length"])).decode("utf-8")
        FakeEndpoint.seen.append({"headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        out = json.dumps(FakeEndpoint.reply).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class RequestTests(unittest.TestCase):
    def test_signature_matches_node_implementation(self):
        body = json.dumps({"a": "ação", "b": [1, 2]}, ensure_ascii=False, separators=(",", ":"))
        js = (
            "import { sign } from './netlify/functions/lib/review-core.mjs';"
            "process.stdout.write(sign(process.argv[1], process.argv[2], process.argv[3]));"
        )
        out = subprocess.run(["node", "--input-type=module", "-e", js, "segredo", "1790000000", body], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, rc.sign("segredo", "1790000000", body))

    def test_blocked_task_never_calls_endpoint(self):
        with tempfile.TemporaryDirectory() as d:
            led, req, out = (os.path.join(d, n) for n in ("l.json", "req.json", "out.json"))
            ledger = g.new_ledger()
            task = g.new_task()
            task["rounds_used"] = 2
            ledger["tasks"]["n1.arte_feed"] = task
            g.save_ledger(ledger, led)
            json.dump(REQ, open(req, "w"))
            r = subprocess.run([sys.executable, SCRIPT, "--request-file", req, "--output-json", out, "--ledger", led],
                               capture_output=True, text=True, env={**os.environ, "CLAUDE_REVIEW_URL": "http://127.0.0.1:9/nunca"})
            self.assertEqual(r.returncode, 10, r.stderr)
            resp = json.load(open(out))
            self.assertEqual((resp["decision"], resp["claude_called"], resp["blocked_reason"]), ("HUMAN_REVIEW_REQUIRED", False, "rounds_exhausted"))

    def test_calls_endpoint_signed_and_updates_queue(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                led, req, out, queue = (os.path.join(d, n) for n in ("l.json", "req.json", "out.json", "q.json"))
                g.save_ledger(g.new_ledger(), led)
                json.dump(REQ, open(req, "w"))
                env = {**os.environ, "CLAUDE_REVIEW_URL": f"http://127.0.0.1:{server.server_port}/", "CLAUDE_REVIEW_KEY": "k", "CLAUDE_REVIEW_HMAC_SECRET": "s"}
                r = subprocess.run([sys.executable, SCRIPT, "--request-file", req, "--output-json", out, "--ledger", led, "--queue", queue, "--update-queue"],
                                   capture_output=True, text=True, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                seen = FakeEndpoint.seen[-1]
                ts = seen["headers"]["x-review-timestamp"]
                self.assertEqual(seen["headers"]["x-review-signature"], rc.sign("s", ts, seen["body"]))
                self.assertEqual(seen["headers"]["x-review-key"], "k")
                self.assertNotIn("HMAC", r.stdout + r.stderr)
                self.assertEqual(json.load(open(queue))["items"]["n1"]["review"]["publish"], "SIM")
        finally:
            server.shutdown()

    def test_missing_config_fails_without_leaking(self):
        with tempfile.TemporaryDirectory() as d:
            led, req, out = (os.path.join(d, n) for n in ("l.json", "req.json", "out.json"))
            g.save_ledger(g.new_ledger(), led)
            json.dump(REQ, open(req, "w"))
            env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_REVIEW")}
            r = subprocess.run([sys.executable, SCRIPT, "--request-file", req, "--output-json", out, "--ledger", led], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 22)
            self.assertIn("CLAUDE_REVIEW_URL", r.stderr)


if __name__ == "__main__":
    unittest.main()
