import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_game_stage
import prepare_windows_restart as restart


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def cache_fixture():
    # Synthetic identities and metadata only: no owner state or game payload.
    manifest = {"schema": 1, "stage": "game-stage-v1", "run": "1" * 32,
                "session": "2" * 32, "challenge": "3" * 32, "source_tag": "4" * 64,
                "files": [{"path": name, "bytes": 100 + i,
                           "sha256": check_game_stage.PINS.get(name, digest(name.encode()))}
                          for i, name in enumerate(sorted(check_game_stage.PATHS))]}
    accepted = {"schema": 1, "result": "copy_observations_accepted", "run_id": manifest["run"],
                "guest_session_id": manifest["session"], "challenge": manifest["challenge"],
                "files": 10, "bytes": sum(item["bytes"] for item in manifest["files"]),
                "executed_source_attested": False, "all_archives_stock_verified": False,
                "save_isolation_verified": False, "offline_license_verified": False,
                "game_launched": False, "launch_authorized": False, "co_op_verified": False}
    return manifest, accepted


class RestartCacheTests(unittest.TestCase):
    def validate(self, manifest, accepted):
        raw = encoded(manifest)
        return restart.validate_cache(raw, encoded(accepted), "1" * 32, digest(raw))

    def test_valid_cache_with_bom_and_full_binary_pins(self):
        manifest, accepted = cache_fixture()
        raw = b"\xef\xbb\xbf" + encoded(manifest)
        self.assertEqual(restart.validate_cache(raw, encoded(accepted), "1" * 32, digest(raw)), manifest)
        self.assertEqual(set(item["path"] for item in manifest["files"]), check_game_stage.PATHS)

    def test_manifest_schema_and_identifiers_are_exact(self):
        manifest, accepted = cache_fixture()
        mutations = ({"schema": True}, {"schema": 1.0}, {"schema": 2}, {"extra": False},
                     {"stage": "startup-v1"}, {"run": "5" * 32}, {"run": "0" * 32},
                     {"session": "invalid"}, {"challenge": "0" * 32},
                     {"source_tag": "A" * 64}, {"source_tag": "0" * 64})
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate({**manifest, **change}, accepted)
        for key in manifest:
            bad = {k: v for k, v in manifest.items() if k != key}
            with self.subTest(missing=key), self.assertRaises(ValueError):
                self.validate(bad, accepted)

    def test_ten_unique_safe_paths_and_exact_file_entry_schema(self):
        manifest, accepted = cache_fixture()
        for path in ("../mgsvtpp.exe", "C:/mgsvtpp.exe", "master/../mgsvtpp.exe",
                     "master\\chunk0.dat", "MGSVTPP.EXE", "steam_api64.dll:stream", "/mgsvtpp.exe"):
            bad = copy.deepcopy(manifest)
            bad["files"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validate(bad, accepted)
        for entries in (manifest["files"][:-1], manifest["files"] + [manifest["files"][0]],
                        [manifest["files"][0]] * 10, {"path": "mgsvtpp.exe"}):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.validate({**manifest, "files": entries}, accepted)
        for change in ({"extra": 1}, {"bytes": True}, {"bytes": 12.0}, {"bytes": 0},
                       {"bytes": -1}, {"bytes": 8 * 1024**3 + 1}, {"sha256": "A" * 64},
                       {"sha256": "1234"}, {"sha256": 0}):
            bad = copy.deepcopy(manifest)
            bad["files"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(bad, accepted)
        bad = copy.deepcopy(manifest)
        del bad["files"][0]["sha256"]
        with self.assertRaises(ValueError):
            self.validate(bad, accepted)

    def test_game_executable_and_steam_dll_must_match_reviewed_pins(self):
        manifest, accepted = cache_fixture()
        for path in ("mgsvtpp.exe", "steam_api64.dll"):
            bad = copy.deepcopy(manifest)
            next(item for item in bad["files"] if item["path"] == path)["sha256"] = "9" * 64
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validate(bad, accepted)

    def test_accepted_identity_totals_flags_and_schema_are_bound(self):
        manifest, accepted = cache_fixture()
        changes = [{"schema": True}, {"schema": 1.0}, {"extra": False},
                   {"result": "files_copied_not_launched"}, {"run_id": "5" * 32},
                   {"guest_session_id": "5" * 32}, {"challenge": "5" * 32},
                   {"files": True}, {"files": 10.0}, {"files": 9},
                   {"bytes": accepted["bytes"] + 1}, {"bytes": float(accepted["bytes"])}]
        for key in ("executed_source_attested", "all_archives_stock_verified", "save_isolation_verified",
                    "offline_license_verified", "game_launched", "launch_authorized", "co_op_verified"):
            changes.extend(({key: True}, {key: 0}, {key: None}))
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(manifest, {**accepted, **change})
        for key in accepted:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                self.validate(manifest, {k: v for k, v in accepted.items() if k != key})

    def test_changed_manifest_hash_and_expected_identity_are_rejected(self):
        manifest, accepted = cache_fixture()
        original = encoded(manifest)
        changed = copy.deepcopy(manifest)
        changed["files"][0]["sha256"] = "8" * 64
        with self.assertRaisesRegex(ValueError, "hash changed"):
            restart.validate_cache(encoded(changed), encoded(accepted), "1" * 32, digest(original))
        for run, expected in (("0" * 32, digest(original)), ("1" * 32, "0" * 64),
                              ("bad", digest(original)), ("1" * 32, digest(original).upper())):
            with self.subTest(run=run, expected=expected), self.assertRaises(ValueError):
                restart.validate_cache(original, encoded(accepted), run, expected)

    def test_oversized_duplicate_key_or_non_object_json_is_rejected(self):
        manifest, accepted = cache_fixture()
        valid = encoded(manifest)
        invalid = (b" " * 8193 + valid, valid.replace(b'"schema":1', b'"schema":1,"schema":1', 1),
                   valid.replace(b'"bytes":100', b'"bytes":100,"bytes":100', 1), b"[]", b"null")
        for raw in invalid:
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                restart.validate_cache(raw, encoded(accepted), "1" * 32, digest(raw))
        for raw in (b" " * 8193 + encoded(accepted),
                    encoded(accepted).replace(b'"schema":1', b'"schema":1,"schema":1', 1), b"[]"):
            with self.subTest(accepted=raw[:80]), self.assertRaises(ValueError):
                restart.validate_cache(valid, raw, "1" * 32, digest(valid))


class RestartPacketTests(unittest.TestCase):
    def generate(self, root, name="packet", source_dir=restart.SOURCES):
        manifest, accepted = cache_fixture()
        manifest_path = Path(root) / "game-stage-manifest.json"
        manifest_path.write_bytes(encoded(manifest))
        manifest_path.with_name("accepted.json").write_bytes(encoded(accepted))
        archive = restart.generate(Path(root) / name, manifest_path, manifest["run"],
                                   digest(manifest_path.read_bytes()), source_dir=source_dir)
        return archive.parent, archive

    def test_standalone_components_are_exact_reviewed_sources(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive = self.generate(root)
            offline = (restart.SOURCES / "GUEST-OFFLINE.txt").read_bytes()
            prelogin = (restart.SOURCES / "Guest-Prelogin.txt").read_bytes()
            self.assertEqual((folder / "Guest-Prelogin.txt").read_bytes(), prelogin)
            self.assertEqual((folder / "GUEST-OFFLINE.txt").read_bytes(), offline)
            prefix = offline[:offline.index(b"    # This is a point-in-time local policy/adapter observation")]
            for phase in ("STAGE", "STARTUP"):
                expected = prefix + (restart.SOURCES / ("GUEST-" + phase + ".tail.txt")).read_bytes()
                self.assertEqual((folder / ("GUEST-" + phase + ".txt")).read_bytes(), expected)

    def test_merged_reviewed_bodies_match_except_explicit_handoffs_and_progress(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive = self.generate(root)
            merged = (folder / "GUEST-SESSION.txt").read_text()
            sources = {"prelogin": "Guest-Prelogin.txt", "offline": "GUEST-OFFLINE.txt",
                       "stage": "GUEST-STAGE.tail.txt", "startup": "GUEST-STARTUP.tail.txt"}
            for phase, source in sources.items():
                body = merged.split("    # BEGIN reviewed " + phase + " component\n", 1)[1]
                body = body.split("    # END reviewed " + phase + " component\n", 1)[0]
                original = (restart.SOURCES / source).read_text()
                if original.startswith("& {\n"):
                    original = original[4:]
                original = original[:-2]
                # Compare the literal reviewed statements after removing only
                # the specifically authorized presentation/progress changes.
                old_lines = [line for line in original.splitlines() if not line.lstrip().startswith("Write-Output ")]
                new_lines = [line for line in body.splitlines() if not line.lstrip().startswith("Write-Output ")]
                if phase == "stage":
                    new_lines = [line for line in new_lines if 'if (Test-Path -LiteralPath "$mgsvInput\\host-error.json")' not in line]
                    new_lines = [line.replace("Copy-MgsvRestartStream $mgsvRead $mgsvWrite $mgsvEntry.bytes $mgsvEntry.path",
                                              "$mgsvRead.CopyTo($mgsvWrite)") for line in new_lines]
                if phase == "startup":
                    body = "\n".join(new_lines)
                    body = re.sub(r"        while \(-not \$mgsvProcess.WaitForExit\(1000\).*?\n        }",
                                  "        while (-not $mgsvProcess.WaitForExit(1000) -and $mgsvClock.Elapsed.TotalSeconds -lt 120) { }",
                                  body, count=1, flags=re.DOTALL)
                    new_lines = [line for line in body.splitlines() if "Write-Progress -Id 2" not in line]
                self.assertEqual(new_lines, old_lines, phase)

    def test_one_literal_paste_block_guards_prompts_and_host_gates_precede_actions(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive = self.generate(root)
            body = (folder / "GUEST-SESSION.txt").read_text()
            self.assertTrue(body.startswith("& {\n"))
            self.assertTrue(body.endswith("\n}\n"))
            self.assertEqual(len(re.findall(r"^& \{", body, re.MULTILINE)), 1)
            for forbidden in ("Invoke-Expression", "ScriptBlock]::Create", "ExecutionPolicy", "EncodedCommand",
                              ". $", "Get-Credential", "Enable-NetAdapter"):
                self.assertNotIn(forbidden, body)
            browser = body.index("-ArgumentList 'https://cdn.akamai.steamstatic.com/")
            installer = body.index("Start-Process -FilePath $mgsvSteamInstaller -PassThru")
            network = body.index("NetSecurity\\Set-NetFirewallProfile")
            game = body.index("[Diagnostics.Process]::Start($mgsvStart)")
            for guard in ("$mgsvIdentity -notmatch", "$PSDefaultParameterValues.Count", "PSSenderInfo",
                          "IsInRole", "$mgsvSessionSource -cne $mgsvRun.session_sha256",
                          "Game data appeared before the fresh offline gate"):
                self.assertLess(body.index(guard), browser)
            self.assertLess(body.index("$mgsvAnswer -cne 'DOWNLOADED') { throw"), installer)
            self.assertLess(body.index("Get-FileHash -LiteralPath $mgsvSteamInstaller"), installer)
            self.assertLess(body.index("Get-AuthenticodeSignature -LiteralPath $mgsvSteamInstaller"), installer)
            self.assertIn("try { $mgsvInstallerProcess.WaitForExit() } finally { $mgsvInstallerProcess.Dispose() }", body)
            self.assertNotIn("Start-Process -FilePath $mgsvSteamInstaller -Wait", body)
            self.assertLess(body.index("$mgsvAnswer -cne 'SIGNIN') { throw"), body.index("# BEGIN reviewed prelogin"))
            signin = body.index("Host prelogin checks accepted. INSIDE guest Steam, sign in normally")
            for guard in ("Wait-MgsvHostFile 'prelogin-accepted.json'", "$mgsvAccepted.session -cne",
                          "$mgsvAccepted.source_tag -cne $mgsvRun.session_sha256", "$mgsvNextOffline.challenge -cne",
                          "$mgsvNextOffline.source_tag -cne $mgsvOfflineSource"):
                self.assertLess(body.index(guard), signin)
            self.assertLess(body.index("$mgsvAnswer -cne 'OFFLINE') { throw"), network)
            self.assertLess(network, body.index("WWQA2"))
            self.assertLess(body.index("WWQA2"), body.index("Wait-MgsvHostFile 'stage-request.json'"))
            self.assertLess(body.index("Wait-MgsvHostFile 'stage-request.json'"), body.index("$mgsvGame = 'C:\\MGSVQA\\Game'"))
            self.assertLess(body.index("Wait-MgsvHostFile 'startup-request.json'"), game)
            self.assertIn("if ($mgsvAnswer -cne 'READY') { return }", body)
            self.assertIn("} finally {\n        Write-Progress -Id 2", body)
            self.assertIn("host-error.json", body)
            self.assertIn("TotalMinutes -gt 60", body)

    def test_progress_is_bounded_and_original_file_hash_verification_remains(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive = self.generate(root)
            body = (folder / "GUEST-SESSION.txt").read_text()
            self.assertIn("[byte[]]::new(4MB)", body)
            self.assertIn("-ge 1000", body)
            self.assertIn("$mgsvCopied -ne $mgsvExpectedBytes", body)
            self.assertIn("Write-Progress -Id 1", body)
            self.assertIn("Write-Progress -Id 2", body)
            self.assertIn("Get-FileHash -LiteralPath $mgsvDestination -Algorithm SHA256", body)
            self.assertIn("$mgsvClock.Elapsed.TotalSeconds -lt 120", body)
            for name in ("GUEST-STAGE.txt", "GUEST-STARTUP.txt"):
                self.assertNotIn("Write-Progress", (folder / name).read_text())

    def test_host_initial_profile_has_only_input_and_output_and_delays_game_staging(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive = self.generate(root)
            host = (folder / "HOST-RESTART.txt").read_text()
            profile = host.split('<Configuration>', 1)[1].split('</Configuration>', 1)[0]
            self.assertEqual(profile.count('<MappedFolder>'), 2)
            self.assertIn('<SandboxFolder>C:\\MGSVQA\\Input</SandboxFolder><ReadOnly>true</ReadOnly>', profile)
            self.assertIn('<SandboxFolder>C:\\MGSVQA\\Output</SandboxFolder><ReadOnly>false</ReadOnly>', profile)
            self.assertNotIn('Game', profile)
            self.assertNotIn('powershell', profile.lower())
            offline_check = host.index('if ([IO.File]::ReadAllText("$mgsvOutput\\offline.gate") -cne $mgsvExpectedOffline)')
            ready_check = host.index('if ([IO.File]::ReadAllText("$mgsvOutput\\stage-ready.gate") -cne $mgsvExpectedReady)')
            staging = host.index("$mgsvGame = Join-Path $mgsvInput 'Game'")
            manifest_write = host.index('Write-MgsvJson "$mgsvInput\\game-stage-manifest.json"')
            self.assertLess(host.index('$mgsvExpectedOffline = "WWQA2'), offline_check)
            self.assertLess(offline_check, ready_check)
            self.assertLess(ready_check, staging)
            self.assertLess(staging, host.index('New-Item -ItemType HardLink'))
            self.assertLess(staging, manifest_write)
            self.assertLess(manifest_write, host.index('Write-MgsvJson "$mgsvInput\\startup-request.json"'))

    def test_package_metadata_host_substitutions_and_zip_bytes_agree(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive_path = self.generate(root)
            metadata = json.loads((folder / "package-manifest.json").read_bytes())
            host = (folder / "HOST-RESTART.txt").read_text()
            self.assertEqual(set(metadata["package_files"]), set(restart.PHASE_FILES))
            for name, expected in metadata["package_files"].items():
                self.assertEqual(expected, digest((folder / name).read_bytes()))
                self.assertIn(expected, host)
            self.assertEqual(metadata["host_sha256"], digest((folder / "HOST-RESTART.txt").read_bytes()))
            self.assertEqual(metadata["cache_manifest_sha256"], digest((Path(root) / "game-stage-manifest.json").read_bytes()))
            self.assertEqual(metadata["cache_run"], "1" * 32)
            self.assertFalse(metadata["executed_source_attested"])
            self.assertNotRegex(host, r"__[A-Z_]+__")
            with zipfile.ZipFile(archive_path) as archive:
                expected_names = {path.name for path in folder.iterdir() if path != archive_path}
                self.assertEqual(set(archive.namelist()), expected_names)
                self.assertEqual(len(archive.namelist()), len(expected_names))
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (folder / name).read_bytes())
                    self.assertNotIn("/", name)
            other, other_archive = self.generate(root, "second-packet")
            self.assertEqual(archive_path.read_bytes(), other_archive.read_bytes())

    def test_generation_refuses_stale_cache_bad_template_or_existing_destination(self):
        with tempfile.TemporaryDirectory() as root:
            folder, archive = self.generate(root)
            before = {path.name: path.read_bytes() for path in folder.iterdir()}
            with self.assertRaises(FileExistsError):
                self.generate(root)
            self.assertEqual(before, {path.name: path.read_bytes() for path in folder.iterdir()})
            source_dir = Path(root) / "sources"
            shutil.copytree(restart.SOURCES, source_dir)
            template = source_dir / "HOST-RESTART.template.txt"
            template.write_text(template.read_text().replace("__CACHE_RUN__", "stale"))
            with self.assertRaisesRegex(ValueError, "missing __CACHE_RUN__"):
                self.generate(root, "bad-template", source_dir)
            self.assertFalse((Path(root) / "bad-template").exists())
            manifest, accepted = cache_fixture()
            accepted["guest_session_id"] = "9" * 32
            (Path(root) / "accepted.json").write_bytes(encoded(accepted))
            manifest_path = Path(root) / "game-stage-manifest.json"
            with self.assertRaisesRegex(ValueError, "stale accepted"):
                restart.generate(Path(root) / "stale", manifest_path, "1" * 32, digest(manifest_path.read_bytes()))
            self.assertFalse((Path(root) / "stale").exists())

    def test_generation_rejects_oversized_cache_before_creating_output(self):
        with tempfile.TemporaryDirectory() as root:
            manifest, accepted = cache_fixture()
            path = Path(root) / "game-stage-manifest.json"
            path.write_bytes(encoded(manifest))
            accepted_path = path.with_name("accepted.json")
            accepted_path.write_bytes(b" " * 8193 + encoded(accepted))
            with self.assertRaisesRegex(ValueError, "oversized cache JSON"):
                restart.generate(Path(root) / "packet", path, manifest["run"], digest(path.read_bytes()))
            self.assertFalse((Path(root) / "packet").exists())


if __name__ == "__main__":
    unittest.main()
