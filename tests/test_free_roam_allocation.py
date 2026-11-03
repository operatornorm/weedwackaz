"""Allocation identity/preservation guards; all package bodies here are synthetic."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import plan_free_roam_allocation as preflight
import mgsv_pack_report as reporter


def pack(members, references=(), kind="fpkd", padding=0):
    data = bytearray(48 + len(members) * 48 + len(references) * 16)
    data[:10] = b"foxfpkdwin" if kind == "fpkd" else b"foxfpk\0win"
    struct.pack_into("<3I", data, 32, 2, len(members), len(references))
    for i, (name, _) in enumerate(members):
        struct.pack_into("<I", data, 48 + i * 48 + 16, len(data))
        struct.pack_into("<I", data, 48 + i * 48 + 24, len(name))
        data[48 + i * 48 + 32:48 + i * 48 + 48] = hashlib.md5(name.encode()).digest()
        data.extend(name.encode() + b"\0")
    for i, name in enumerate(references):
        at = 48 + len(members) * 48 + i * 16
        struct.pack_into("<I", data, at, len(data))
        struct.pack_into("<I", data, at + 8, len(name))
        data.extend(name.encode() + b"\0")
    data.extend(bytes(padding))
    for i, (_, body) in enumerate(members):
        struct.pack_into("<I", data, 48 + i * 48, len(data))
        struct.pack_into("<I", data, 48 + i * 48 + 8, len(body))
        data.extend(body)
    struct.pack_into("<I", data, 10, len(data))
    return bytes(data)


def fixture():
    manifest = preflight.read_json(preflight.MANIFEST)
    nodes, blobs = [], {}
    for target in manifest["targets"]:
        allocator = ("SYNTHETIC_" + target["id"]).encode()
        data = pack([(target["member"], allocator), ("/Assets/test/unrelated.bin", b"PRIVATE_BODY")])
        blobs[target["id"]] = data
        metadata = reporter.inspect(data)
        target.update(package_sha256=metadata["container_sha256"], member_count=2,
                      member_size=len(allocator), member_sha256=hashlib.sha256(allocator).hexdigest())
        loader = pack([("/Assets/test/loader.bin", b"SYNTHETIC")], kind="fpk")
        loader_metadata = reporter.inspect(loader)
        target["loader_pack_sha256"] = loader_metadata["container_sha256"]
        for name, content in ((target["loader_pack"], loader_metadata), (target["package"], metadata)):
            nodes.append({"archive": target["archive"], "path": name, "hash": "%016x" % reporter.path_hash(name),
                          "depth": 0, "entry": len(nodes), "status": "metadata_ok",
                          "checksum_stage": "decoded_payload", "metadata": content})
    report = {"kind": "mgsv_pack_metadata_only_not_gameplay_validation", "version": "python-2",
              "executable_sha256": manifest["executable_sha256"], "enumeration_finished": True,
              "limits_hit": 0, "parse_failures": 0, "containers_failed": 0, "containers_inspected": len(nodes),
              "probes": [{"path": node["path"], "matches": 1} for node in nodes],
              "containers": nodes, "archives": [{"archive": name, "status": "indexed", "version": 1,
                                                   "entries": 100} for name in sorted(preflight.ARCHIVES)]}
    return report, manifest, blobs


class AllocationPreflightTests(unittest.TestCase):
    def test_complete_plan_is_non_applicable_deterministic_and_does_not_mutate_inputs(self):
        report, manifest, _ = fixture()
        before = copy.deepcopy((report, manifest))
        plan = preflight.build_plan(report, manifest)
        self.assertEqual(plan, preflight.build_plan(report, manifest))
        self.assertEqual((report, manifest), before)
        self.assertIs(plan["can_apply"], False)
        self.assertEqual(len(plan["operations"]), 3)
        self.assertEqual(len(plan["shared_support_members"]), 3)
        self.assertNotIn(plan["excluded_shared_controller"], plan["shared_support_members"])
        self.assertTrue(all(operation["proposed_expand"]["parts_slots"] == 2 for operation in plan["operations"]))
        self.assertNotIn("PRIVATE_BODY", json.dumps(plan))

    def test_incomplete_or_wrong_identity_report_is_rejected(self):
        report, manifest, _ = fixture()
        for key, value in (("limits_hit", 1), ("parse_failures", 1), ("containers_failed", 1),
                           ("enumeration_finished", False), ("containers_inspected", 999),
                           ("version", "python-1"), ("executable_sha256", "0" * 64), ("limits_hit", False)):
            with self.subTest(key=key, value=value):
                mutant = copy.deepcopy(report)
                mutant[key] = value
                with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)
        for update in ({"status": "archive_parse_or_read_failed"}, {"version": True}):
            mutant = copy.deepcopy(report)
            mutant["archives"][0].update(update)
            with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)

    def test_missing_duplicate_or_override_package_is_rejected(self):
        report, manifest, _ = fixture()
        for kind in ("missing", "duplicate", "override"):
            with self.subTest(kind=kind):
                mutant = copy.deepcopy(report)
                if kind == "missing": mutant["containers"].pop(3)
                else:
                    extra = copy.deepcopy(mutant["containers"][1])
                    if kind == "override": extra["archive"] = "master/0/00.dat"
                    mutant["containers"].append(extra)
                mutant["containers_inspected"] = len(mutant["containers"])
                with self.assertRaisesRegex(ValueError, "package_occurrence_count"):
                    preflight.build_plan(mutant, manifest)

    def test_wrong_archive_hash_depth_entry_or_checksum_is_rejected(self):
        report, manifest, _ = fixture()
        for key, value in (("archive", "master/chunk1.dat"), ("hash", "0" * 16), ("depth", 1),
                           ("depth", False), ("entry", 100), ("entry", True), ("checksum_stage", "unchecked")):
            with self.subTest(key=key):
                mutant = copy.deepcopy(report)
                mutant["containers"][1][key] = value
                with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)

    def test_contradictory_probes_and_archive_entry_aliases_are_rejected(self):
        report, manifest, _ = fixture()
        for kind in ("missing_probe", "duplicate_probe", "two_matches", "boolean_matches", "aliased_entry"):
            with self.subTest(kind=kind):
                mutant = copy.deepcopy(report)
                if kind == "missing_probe": mutant["probes"].pop(1)
                elif kind == "duplicate_probe": mutant["probes"].append(copy.deepcopy(mutant["probes"][1]))
                elif kind == "two_matches": mutant["probes"][1]["matches"] = 2
                elif kind == "boolean_matches": mutant["probes"][1]["matches"] = True
                else: mutant["containers"][0]["entry"] = mutant["containers"][1]["entry"]
                with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)

    def test_container_and_member_fingerprints_are_separate_mandatory_checks(self):
        report, manifest, _ = fixture()
        for scope, key in (("metadata", "container_sha256"), ("member", "stored_member_sha256")):
            mutant = copy.deepcopy(report)
            metadata = mutant["containers"][1]["metadata"]
            (metadata if scope == "metadata" else metadata["members"][0])[key] = "0" * 64
            with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)

    def test_duplicate_alternate_or_existing_replacement_allocator_is_rejected(self):
        report, manifest, _ = fixture()
        for kind in ("duplicate", "alternate", "replacement"):
            with self.subTest(kind=kind):
                mutant, expected = copy.deepcopy(report), copy.deepcopy(manifest)
                members = mutant["containers"][1]["metadata"]["members"]
                if kind == "duplicate":
                    members.append(copy.deepcopy(members[0]))
                    expected["targets"][0]["member_count"] += 1
                else:
                    members[1]["name"] = (preflight.PREFIX + "other_instance.fox2" if kind == "alternate"
                                          else preflight.SHARED_MEMBERS[2])
                with self.assertRaises(ValueError): preflight.build_plan(mutant, expected)

    def test_redacted_names_bad_spans_and_duplicate_references_are_rejected(self):
        report, manifest, _ = fixture()
        for key, value in (("name", "<name omitted>"), ("offset", -1), ("size", reporter.MAX_PACK),
                           ("offset", True)):
            mutant = copy.deepcopy(report)
            mutant["containers"][1]["metadata"]["members"][1][key] = value
            with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)
        mutant = copy.deepcopy(report)
        mutant["containers"][1]["metadata"]["references"] = ["/Assets/test/repeat.fpk"] * 2
        with self.assertRaises(ValueError): preflight.build_plan(mutant, manifest)

    def test_live_bytes_must_match_and_are_never_modified(self):
        _, manifest, blobs = fixture()
        target = manifest["targets"][0]
        blob = blobs[target["id"]]
        preflight.verify_live_package(blob, target)
        self.assertEqual(blob, blobs[target["id"]])
        changed = blob[:-1] + bytes([blob[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "package_fingerprint"):
            preflight.verify_live_package(changed, target)
        with self.assertRaises(ValueError): preflight.verify_live_package(blob, manifest["targets"][1])

    def test_preservation_allows_offsets_to_move_but_preserves_unknown_payloads_and_metadata(self):
        removed = preflight.PREFIX + "single_player2_instance.fox2"
        kept = [("/Assets/test/a.bin", b"UNKNOWN_A"), ("/Assets/test/b.bin", b"UNKNOWN_B")]
        refs = ["/Assets/test/external.fpk"]
        before = pack([kept[0], (removed, b"SYNTHETIC_ALLOCATOR"), kept[1]], refs)
        after = pack(kept, refs, padding=32)
        preflight.verify_preservation(before, after, removed)
        self.assertNotEqual(reporter.inspect(before)["members"][0]["offset"],
                            reporter.inspect(after)["members"][0]["offset"])
        bad_md5 = bytearray(after)
        bad_md5[48 + 32] ^= 1
        bad_header = bytearray(after)
        bad_header[14] ^= 1
        for mutant in (pack(kept[::-1], refs), pack(kept[:1], refs),
                       pack([(kept[0][0], b"CHANGED"), kept[1]], refs),
                       pack(kept + [("/Assets/test/extra.bin", b"EXTRA")], refs),
                       pack(kept, ["/Assets/test/changed.fpk"]), bytes(bad_md5), bytes(bad_header), before):
            with self.assertRaises(ValueError): preflight.verify_preservation(before, mutant, removed)

    def test_cli_preserves_existing_output_and_rejects_duplicate_json_fields(self):
        report, manifest, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, expected, output = root / "input.json", root / "manifest.json", root / "plan.json"
            source.write_text(json.dumps(report))
            expected.write_text(json.dumps(manifest))
            with mock.patch.object(preflight, "MANIFEST", expected), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(preflight.main(["--report", str(source), "--output", str(output)]), 0)
                original = output.read_bytes()
                self.assertEqual(preflight.main(["--report", str(source), "--output", str(output)]), 1)
                self.assertEqual(output.read_bytes(), original)
            source.write_text('{"same":1,"same":2}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_field"): preflight.read_json(source)

    def test_overlapping_member_spans_cannot_exceed_hashing_budget(self):
        data = bytearray(pack([(preflight.PREFIX + "a_instance.fox2", b"a" * 100),
                               (preflight.PREFIX + "b_instance.fox2", b"b" * 100)]))
        # Both individually valid spans now alias the same100 bytes.
        struct.pack_into("<I", data, 48 + 48, reporter.get32(data, 48))
        with mock.patch.object(preflight, "MAX_PRESERVATION_BYTES", 150), \
                mock.patch.object(preflight, "inspect") as inspect:
            with self.assertRaisesRegex(ValueError, "preservation_hash_budget"):
                preflight.preservation_snapshot(bytes(data))
            inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
