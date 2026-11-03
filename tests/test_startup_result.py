import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("startup", Path(__file__).resolve().parents[1] / "tools/check_startup_result.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(schema=1, stage="startup-v1", run="1" * 32, session="2" * 32, challenge="3" * 32, source_tag="4" * 64, manifest_sha256="5" * 64, result_sha256="6" * 64)
        self.report = {key: self.request[key] for key in ("schema", "stage", "run", "session", "challenge", "source_tag")}
        self.report.update(result="process_survived_deadline", process_started=True, observed_seconds=120, exit_code_hex="00000001", native_error=None, close_method="forced", **{key: False for key in startup.PROOFS})
        self.copied = dict(result="copy_observations_accepted", run_id="1" * 32, guest_session_id="2" * 32)

    def check(self):
        return startup.check(json.dumps(self.request).encode(), json.dumps(self.report).encode(), self.copied, "4" * 64, "5" * 64, "6" * 64)

    def test_survival_grants_no_gameplay_license_or_save_proof(self):
        result = self.check()
        self.assertEqual(result["outcome"], "process_survived_deadline")
        for key in startup.PROOFS: self.assertIs(result[key], False)
        self.report.update(result="exited_before_deadline", observed_seconds=1, close_method="not_needed", exit_code_hex="C0000135")
        self.assertEqual(self.check()["exit_code_hex"], "C0000135")

    def test_bad_bindings_or_proof_claims_reject(self):
        for key, value in (("session", "7" * 32), ("challenge", "8" * 32), ("stage", "game-stage-v1"), ("source_tag", "9" * 64), ("gameplay_verified", True), ("save_isolation_verified", 0)):
            previous = self.report[key]; self.report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check()
            self.report[key] = previous
        self.request["manifest_sha256"] = "a" * 64
        with self.assertRaises(ValueError): self.check()

    def test_inconsistent_results_extra_fields_oversized_and_duplicate_keys_reject(self):
        original = copy.deepcopy(self.report)
        for key, value in (("observed_seconds", 131), ("observed_seconds", True), ("process_started", False), ("close_method", "failed"), ("exit_code_hex", "hello"), ("window_title", "private")):
            self.report = copy.deepcopy(original); self.report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check()
        for raw in (b" " * 2049, b'{"schema":1,"schema":1}'):
            with self.subTest(raw_len=len(raw)), self.assertRaises(ValueError): startup.decode(raw)


if __name__ == "__main__": unittest.main()
