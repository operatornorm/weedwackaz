import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("game_stage", Path(__file__).resolve().parents[1] / "tools/check_game_stage.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class GameStageTests(unittest.TestCase):
    def setUp(self):
        self.offline = {"result": "local_network_cut_observations_accepted", "run_id": "1" * 32, "guest_session_id": "2" * 32}
        self.manifest = {"schema": 1, "stage": "game-stage-v1", "run": "1" * 32, "session": "2" * 32,
                         "challenge": "3" * 32, "source_tag": "4" * 64,
                         "files": [{"path": name, "bytes": 20, "sha256": stage.PINS.get(name, "5" * 64)} for name in sorted(stage.PATHS)]}
        self.report = copy.deepcopy(self.manifest)
        self.report["result"] = "files_copied_not_launched"

    def check(self):
        return stage.check(json.dumps(self.manifest).encode(), json.dumps(self.report).encode(), self.offline, "4" * 64)

    def test_copy_observation_grants_no_launch_licensing_or_gameplay_claim(self):
        result = self.check()
        self.assertEqual(result["files"], 10)
        self.assertEqual(result["bytes"], 200)
        for key in ("launch_authorized", "offline_license_verified", "all_archives_stock_verified", "save_isolation_verified", "co_op_verified"):
            self.assertFalse(result[key])

    def test_wrong_session_phase_source_challenge_or_content_rejects(self):
        for key, value in (("session", "6" * 32), ("stage", "offline"), ("source_tag", "7" * 64), ("challenge", "8" * 32)):
            with self.subTest(key=key):
                old = self.report[key]
                self.report[key] = value
                with self.assertRaises(ValueError): self.check()
                self.report[key] = old
        self.report["files"][0]["sha256"] = "9" * 64
        with self.assertRaises(ValueError): self.check()

    def test_matching_bad_paths_duplicates_sizes_and_binary_substitution_reject(self):
        original = copy.deepcopy(self.manifest)
        for key, value in (("path", "../userdata/save"), ("path", "C:/Windows/x"), ("bytes", -1), ("bytes", True), ("bytes", 9 * 1024**3), ("sha256", "z" * 64)):
            self.manifest = copy.deepcopy(original)
            self.manifest["files"][0][key] = value
            self.report = dict(copy.deepcopy(self.manifest), result="files_copied_not_launched")
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.check()
        for mutation in ("duplicate", "binary"):
            self.manifest = copy.deepcopy(original)
            if mutation == "duplicate": self.manifest["files"][0] = copy.deepcopy(self.manifest["files"][1])
            else:
                next(item for item in self.manifest["files"] if item["path"] == "mgsvtpp.exe")["sha256"] = "f" * 64
            self.report = dict(copy.deepcopy(self.manifest), result="files_copied_not_launched")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.check()

    def test_oversized_or_duplicate_key_json_rejects(self):
        for raw in (b" " * 8193, b'{"schema":1,"schema":1}'):
            with self.subTest(raw_len=len(raw)), self.assertRaises(ValueError): stage.decode(raw)


if __name__ == "__main__": unittest.main()
