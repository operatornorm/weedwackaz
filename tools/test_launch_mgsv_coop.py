"""Launcher-routing tests with a stand-in process; these do not test MGSV."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LAUNCHER = Path(__file__).with_name("launch_mgsv_coop.py")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "co-op copy with spaces"
        self.game.mkdir()
        (self.game / "mgsvtpp.exe").write_bytes(b"stand-in executable identity")
        (self.game / "dinput8.dll").write_bytes(b"stand-in mod presence")
        self.prefix = self.root / "linux data" / "compatdata"
        self.result = self.root / "captured.json"
        self.child = self.root / "capture.py"
        self.child.write_text(
            "import json,os,sys\n"
            "from pathlib import Path\n"
            "Path(sys.argv[1]).write_text(json.dumps({"
            "'args':sys.argv[2:], 'cwd':os.getcwd(),"
            "'prefix':os.environ['STEAM_COMPAT_DATA_PATH'],"
            "'app':os.environ['SteamAppId'],"
            "'overrides':os.environ['WINEDLLOVERRIDES'],"
            "'mounts':os.environ['STEAM_COMPAT_MOUNTS']}))\n",
            encoding="utf-8")

    def run_launcher(self, tail=None, options=(), env_updates=None):
        env = dict(os.environ, SteamAppId="287700",
                   STEAM_COMPAT_DATA_PATH=str(self.root / "original-prefix"),
                   STEAM_COMPAT_MOUNTS="/existing-mount", WINEDLLOVERRIDES="dxgi=n")
        if env_updates:
            env.update(env_updates)
        if tail is None:
            tail = ["/original install/mgsvtpp.exe"]
        return subprocess.run(
            [sys.executable, str(LAUNCHER), "--game-dir", str(self.game),
             "--prefix", str(self.prefix), *options, "--", sys.executable,
             str(self.child), str(self.result), *tail],
            env=env, capture_output=True, text=True, timeout=10)

    def test_routes_only_executable_and_preserves_literal_arguments(self):
        literal = "spaces ; $(never-run) 'quotes'"
        proc = self.run_launcher(["/original install/mgsvtpp.exe", literal])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(self.result.read_text())
        self.assertEqual(result["args"], [str(self.game / "mgsvtpp.exe"), literal])
        self.assertEqual(result["cwd"], str(self.game))
        self.assertEqual(result["prefix"], str(self.prefix))
        self.assertEqual(result["app"], "287700")
        self.assertEqual(result["overrides"], "dxgi=n;dinput8.dll=n,b")
        self.assertEqual(result["mounts"], "/existing-mount:" + str(self.game))
        self.assertTrue((self.prefix.parent / "last-launch.json").is_file())

    def test_dry_run_does_not_launch_or_create_prefix(self):
        (self.game / "dinput8.dll").unlink()
        proc = self.run_launcher(options=["--dry-run"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["game_executable"],
                         str(self.game / "mgsvtpp.exe"))
        self.assertFalse(self.prefix.parent.exists())
        self.assertFalse(self.result.exists())

    def test_missing_or_ambiguous_game_argument_never_launches(self):
        for args in (["other.exe"], ["a/mgsvtpp.exe", "b/mgsvtpp.exe"]):
            with self.subTest(args=args):
                proc = self.run_launcher(args)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(self.result.exists())
                self.assertFalse(self.prefix.parent.exists())

    def test_hash_mismatch_prevents_launch(self):
        proc = self.run_launcher(options=["--expected-sha256", "0" * 64])
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.result.exists())

    def test_expected_hash_allows_launch(self):
        digest = hashlib.sha256((self.game / "mgsvtpp.exe").read_bytes()).hexdigest()
        proc = self.run_launcher(options=["--expected-sha256", digest])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.result.exists())

    def test_missing_mod_prevents_real_launch(self):
        (self.game / "dinput8.dll").unlink()
        proc = self.run_launcher()
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.result.exists())

    def test_conflicting_override_prevents_launch(self):
        proc = self.run_launcher(env_updates={"WINEDLLOVERRIDES": "dinput8=b"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.result.exists())

    def test_original_or_game_local_prefix_is_rejected(self):
        proc = self.run_launcher(env_updates={"STEAM_COMPAT_DATA_PATH": str(self.prefix)})
        self.assertNotEqual(proc.returncode, 0)
        self.prefix = self.game / "prefix"
        proc = self.run_launcher()
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.result.exists())


if __name__ == "__main__":
    unittest.main()
