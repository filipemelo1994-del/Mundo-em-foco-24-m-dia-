import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "update_publish_queue.py")


def run(queue, *args):
    return subprocess.run([sys.executable, SCRIPT, "--queue", queue, *args], capture_output=True, text=True)


class QueueTests(unittest.TestCase):
    def test_existing_behaviour_is_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            q = os.path.join(d, "q.json")
            r = run(q, "--id", "n1", "--state", "FEED_PENDENTE", "--feed-art", "--story-art", "--error", "")
            self.assertEqual(r.returncode, 0, r.stderr)
            item = json.load(open(q))["items"]["n1"]
            self.assertEqual((item["state"], item["feed_art"], item["story_art"], item["last_error"]), ("FEED_PENDENTE", True, True, None))
            self.assertNotIn("review", item)
            self.assertNotIn("art_validation", item)
            run(q, "--id", "n1", "--increment", "feed")
            self.assertEqual(json.load(open(q))["items"]["n1"]["attempts"]["feed"], 1)

    def test_review_json_sets_human_review_state(self):
        with tempfile.TemporaryDirectory() as d:
            q, resp = os.path.join(d, "q.json"), os.path.join(d, "r.json")
            run(q, "--id", "n1", "--state", "FEED_PENDENTE")
            json.dump({"task_id": "n1.arte_feed", "round": 2, "decision": "HUMAN_REVIEW_REQUIRED", "next_action": "HUMAN_REVIEW_REQUIRED",
                       "rounds_used": 2, "review_file": "data/reviews/n1.arte_feed-r2.json"}, open(resp, "w"))
            self.assertEqual(run(q, "--id", "n1", "--review-json", resp).returncode, 0)
            item = json.load(open(q))["items"]["n1"]
            self.assertEqual(item["state"], "HUMAN_REVIEW_REQUIRED")
            self.assertEqual(item["review"]["previous_state"], "FEED_PENDENTE")
            self.assertEqual(item["review"]["rounds_used"], 2)

    def test_review_ok_keeps_state(self):
        with tempfile.TemporaryDirectory() as d:
            q, resp = os.path.join(d, "q.json"), os.path.join(d, "r.json")
            run(q, "--id", "n1", "--state", "FEED_PENDENTE")
            json.dump({"task_id": "n1.arte_feed", "round": 1, "decision": "REVIEWED", "next_action": "PUBLISH_IF_VALIDATOR_PASSES",
                       "review": {"status": "OK", "publish": "SIM"}}, open(resp, "w"))
            run(q, "--id", "n1", "--review-json", resp)
            item = json.load(open(q))["items"]["n1"]
            self.assertEqual(item["state"], "FEED_PENDENTE")
            self.assertEqual((item["review"]["status"], item["review"]["publish"]), ("OK", "SIM"))

    def test_art_validation_records_failed_checks(self):
        with tempfile.TemporaryDirectory() as d:
            q, rep = os.path.join(d, "q.json"), os.path.join(d, "v.json")
            json.dump({"passed": False, "sha256": "ab" * 32, "checks": [
                {"id": "dimensions", "result": "pass"}, {"id": "not_equal_to_master", "result": "fail"}]}, open(rep, "w"))
            run(q, "--id", "n1", "--art-validation", rep, "--art-sha256", "ab" * 32, "--state", "ARTE_BLOQUEADA")
            item = json.load(open(q))["items"]["n1"]
            self.assertEqual(item["art_validation"]["failed"], ["not_equal_to_master"])
            self.assertFalse(item["art_validation"]["passed"])
            self.assertEqual((item["state"], item["art_sha256"]), ("ARTE_BLOQUEADA", "ab" * 32))


if __name__ == "__main__":
    unittest.main()
