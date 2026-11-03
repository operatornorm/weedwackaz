"""Bounded FOX2 inspection and pure transform checks; fixtures contain no owner data."""

import contextlib
import copy
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import inspect_free_roam_controllers as check
import mgsv_fox2 as fox
import mgsv_pack_report as qar
import plan_free_roam_allocation as identity
from test_free_roam_allocation import pack
from test_mgsv_pack_report import outer_encode

FIXTURES = Path(__file__).resolve().parents[1] / "build-cache/controller-fixtures"


def archive(entries):
    """Independent small v1 archive builder; real producer fixtures are tested separately."""
    header = bytearray(1024)
    header[:4] = b"SQAR"
    for at, value, mask in ((4, 0, qar.XOR[0]), (8, len(entries), qar.XOR[1]), (24, 1, qar.XOR[0])):
        struct.pack_into("<I", header, at, value ^ mask)
    for i, (name, payload) in enumerate(entries):
        at = len(header)
        section = (at >> 10) << 40
        a, b = section & 0xffffffff, section >> 32
        struct.pack_into("<II", header, 32 + i * 8,
                         a ^ qar.XOR[(i + i * 8 // 5) % 4], b ^ qar.XOR[(i + (i * 8 + 4) // 5) % 4])
        checksum = hashlib.md5(payload).digest()
        row = struct.pack("<QII", qar.path_hash(name) ^ 0x4144104341441043,
                          len(payload) ^ qar.XOR[1], len(payload) ^ qar.XOR[2])
        row += struct.pack("<4I", *(qar.get32(checksum, j * 4) ^ mask
                                   for j, mask in enumerate((qar.XOR[3], qar.XOR[0], qar.XOR[0], qar.XOR[1]))))
        header.extend(row + outer_encode(payload, checksum, name_hash=qar.path_hash(name)))
        header.extend(bytes((-len(header)) % 1024))
    return bytes(header)


def copied_game(root, matching_profiles=False):
    manifest = identity.read_json(identity.MANIFEST)
    executable = b"SYNTHETIC_EXECUTABLE"
    (root / "mgsvtpp.exe").write_bytes(executable)
    manifest["executable_sha256"] = hashlib.sha256(executable).hexdigest()
    sources = {name: [] for name in identity.ARCHIVES}
    for target in manifest["targets"]:
        name = "synthetic_single.fox2"
        if matching_profiles:
            name = "synthetic_profile_" + ("NormalScarf" if target["parts_profile_hash"] == "0000c94e97c2d50c" else "Normal") + ".fox2"
        body = (FIXTURES / name).read_bytes()
        package = pack([(target["member"], body), ("/Assets/test/preserve.bin", b"PRIVATE_BODY")])
        loader = pack([("/Assets/test/loader.bin", b"SYNTHETIC")], kind="fpk")
        target.update(package_sha256=hashlib.sha256(package).hexdigest(), loader_pack_sha256=hashlib.sha256(loader).hexdigest(),
                      member_sha256=hashlib.sha256(body).hexdigest(), member_size=len(body), member_count=2)
        sources[target["archive"]] += [(target["loader_pack"], loader), (target["package"], package)]
    for name, entries in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive(entries))
        path.chmod(0o400)
    return manifest


class ControllerPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (FIXTURES / "reference.json").is_file():
            raise AssertionError("Prepare pinned controller fixtures with build-support/prepare_controller_fixtures.go first")

    def test_strcode64_agrees_with_pinned_go_vectors(self):
        reference = json.loads((FIXTURES / "reference.json").read_text())
        for text, expected in reference["hash_vectors"].items():
            self.assertEqual("%012x" % fox.strcode64(text), expected)
        self.assertEqual(fox.strcode64("name"), 0x3391ed17a03a)
        with self.assertRaises(ValueError): fox.strcode64("x" * 128)

    def test_independent_foxtool_fixtures_agree_with_go_reader(self):
        reference = json.loads((FIXTURES / "reference.json").read_text())
        for item in reference["fixtures"]:
            with self.subTest(file=item["file"]):
                tree = fox.parse_fox2((FIXTURES / item["file"]).read_bytes())
                self.assertEqual(len(tree["entities"]), len(item["entities"]))
                for actual, expected in zip(tree["entities"], item["entities"]):
                    self.assertEqual(actual["class_hash"], expected["class_hash"])
                    self.assertEqual([{"hash":p["name_hash"], "type":p["datatype"], "container":p["container"],
                                       "count":len(p["values"])} for p in actual["properties"]], expected["properties"])
        # A separate stock game fixture legitimately omits the empty-string literal.
        tree = fox.parse_fox2((FIXTURES / "additional_parts.fox2").read_bytes())
        self.assertNotIn(fox.strcode64(""), tree["literals"])
        self.assertEqual(fox.literal(tree, fox.strcode64("")), "")

    def test_all_four_mod_reference_members_parse_but_are_not_single_slot_stock(self):
        for name in ("two_player2_instances", "player2_additional_parts_x1", "player2_online_motion", "player2_mtbs_motion_loader"):
            tree = fox.parse_fox2((FIXTURES / (name + ".fox2")).read_bytes())
            with self.assertRaises(ValueError): fox.validate_single_slot(tree)
        tree = fox.parse_fox2((FIXTURES / "synthetic_single.fox2").read_bytes())
        self.assertTrue(fox.validate_single_slot(tree))
        summary = fox.controller_summary(tree)
        self.assertEqual(summary["controller_count"], 1)
        self.assertEqual(summary["selected_fields"]["configuration_partsBlockCount"]["values"], [1])

    def test_malformed_sections_counts_properties_literals_and_footer_fail_closed(self):
        original = (FIXTURES / "synthetic_single.fox2").read_bytes()
        mutations = [(0, "I", 0), (8, "I", 65), (12, "I", 32), (16, "I", 31),
                     (32, "h", 52), (32 + 40, "i", -1), (32 + 44, "i", 16), (32 + 48, "i", 0x7fffffff),
                     (32 + 64 + 8, "B", 255), (32 + 64 + 9, "B", 0x80),
                     (32 + 64 + 10, "h", -1), (32 + 64 + 12, "h", 31), (32 + 64 + 14, "H", 33)]
        for offset, fmt, value in mutations:
            mutant = bytearray(original)
            struct.pack_into("<" + fmt, mutant, offset, value)
            with self.subTest(offset=offset):
                with self.assertRaises(ValueError): fox.parse_fox2(bytes(mutant))
        strings = qar.get32(original, 12)
        for offset, fmt, value in ((strings, "Q", 1), (strings + 8, "i", -1), (strings + 8, "i", 128)):
            mutant = bytearray(original)
            struct.pack_into("<" + fmt, mutant, offset, value)
            with self.assertRaises(ValueError): fox.parse_fox2(bytes(mutant))
        for blob in (original[:-1], original + bytes(16), original[:-1] + b"x"):
            with self.assertRaises(ValueError): fox.parse_fox2(blob)

    def test_graph_uses_addresses_and_rejects_ambiguity_or_null_children(self):
        original = fox.parse_fox2((FIXTURES / "synthetic_single.fox2").read_bytes())
        # ID zero is legitimate; graph links use Address, independently of IDs.
        for entity in original["entities"]: entity["id"] = 0
        fox.validate_single_slot(original)
        for kind in ("backlink", "null_child", "wrong_map_key", "dataset_name_type", "duplicate_property"):
            tree = copy.deepcopy(original)
            dataset, controller, _ = tree["entities"]
            if kind == "backlink": fox.prop(controller, "dataSet", 21, 0, 1)["values"] = [123]
            elif kind == "null_child": controller["address"] = 0
            elif kind == "wrong_map_key": fox.prop(dataset, "dataList", 13, 2)["keys"][0] = 123
            elif kind == "dataset_name_type": fox.prop(dataset, "name", 11, 0, 1)["datatype"] = 5
            else: controller["properties"].append(copy.deepcopy(controller["properties"][0]))
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError): fox.validate_single_slot(tree)

    def test_summary_redacts_unexpected_class_literals_and_all_raw_data(self):
        tree = fox.parse_fox2((FIXTURES / "synthetic_single.fox2").read_bytes())
        value = "PRIVATE_USERNAME"
        key = fox.strcode64(value)
        tree["entities"][2]["class_hash"] = key
        tree["literals"][key] = value
        encoded = json.dumps(fox.controller_summary(tree))
        self.assertNotIn(value, encoded)
        self.assertIn("/Assets/tpp/pack/player/game_object/synthetic_single.fpk", encoded)
        self.assertNotIn("literals", encoded)
        self.assertIn("<unrecognized>", encoded)
        controller = tree["entities"][1]
        p = fox.prop(controller, "name", 11, 0, 1)
        p.update(datatype=5, values=[123456789])
        self.assertNotIn("values", fox.controller_summary(tree)["selected_fields"]["name"])
        path = fox.prop(controller, "instanceSettings_instancePackagePath", 11, 0, 1)
        private = "C:/Users/PRIVATE_USERNAME/token"
        key = fox.strcode64(private)
        tree["literals"][key] = private
        path["values"] = [key]
        encoded = json.dumps(fox.controller_summary(tree))
        self.assertNotIn(private, encoded)
        self.assertNotIn("PRIVATE_USERNAME", encoded)
        self.assertIn("<value omitted>", encoded)

    def test_pure_transform_removes_one_row_and_preserves_other_members_references_and_input(self):
        member = "/Assets/tpp/level_asset/chara/player/game_object/single_player2_instance.fox2"
        body = (FIXTURES / "synthetic_single.fox2").read_bytes()
        source = pack([("/Assets/test/a.bin", b"BEFORE"), (member, body), ("/Assets/test/b.bin", b"AFTER")],
                      ["/Assets/test/external.fpk"])
        target = {"package_sha256":hashlib.sha256(source).hexdigest(), "member":member, "member_count":3,
                  "member_sha256":hashlib.sha256(body).hexdigest(), "member_size":len(body)}
        original = bytes(source)
        output = check.transform_verified_package(source, target)
        self.assertEqual(source, original)
        identity.verify_preservation(source, output, member)
        self.assertEqual(len(output), len(source))
        self.assertEqual([m["name"] for m in qar.inspect(output)["members"]], ["/Assets/test/a.bin", "/Assets/test/b.bin"])
        self.assertEqual(qar.inspect(output)["references"], ["/Assets/test/external.fpk"])
        # Byte allowlist: entry-count field and compacted table only. All bodies/names stay unchanged.
        old_end = 48 + 3 * 48 + 16
        self.assertEqual(source[:36], output[:36])
        self.assertEqual(source[40:48], output[40:48])
        self.assertEqual(source[old_end:], output[old_end:])
        with self.assertRaises(ValueError): check.transform_verified_package(output, target)
        changed = source[:-1] + bytes([source[-1] ^ 1])
        with self.assertRaises(ValueError): check.transform_verified_package(changed, target)

    def test_end_to_end_check_is_read_only_and_export_contains_no_bodies_or_pc_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = copied_game(root)
            paths = list(root.rglob("*"))
            before = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
            result = check.collect(root, manifest)
            self.assertEqual(result["structures_matching_policy"], 3)
            self.assertEqual(result["structures_requiring_review"], 0)
            self.assertFalse(result["can_install"])
            after = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
            self.assertEqual(before, after)
            encoded = json.dumps(result)
            self.assertNotIn(directory, encoded)
            self.assertNotIn("PRIVATE_BODY", encoded)
            self.assertNotIn("literals", encoded)
            self.assertEqual(len(list(root.rglob("*"))), len(paths))
            # Conflicting override must reject identity rather than selecting archive precedence.
            target = manifest["targets"][0]
            override = root / "master/0/00.dat"
            override.chmod(0o600)
            override.write_bytes(archive([(target["package"], b"CONFLICTING_OVERRIDE")]))
            result = check.collect(root, manifest)
            self.assertEqual(result["controllers"][0]["failure_code"], "package_occurrence_count")

    def test_cli_output_guard_and_wrong_executable_preserve_game_and_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "copy"
            root.mkdir()
            (root / "mgsvtpp.exe").write_bytes(b"WRONG_EXECUTABLE")
            output = Path(directory) / "report.json"
            manifest = identity.read_json(identity.MANIFEST)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check.main(["--game-dir",str(root),"--output",str(root / "bad.json")],manifest),1)
                self.assertEqual(check.main(["--game-dir",str(root),"--output",str(output)],manifest),0)
                original = output.read_bytes()
                self.assertEqual(check.main(["--game-dir",str(root),"--output",str(output)],manifest),1)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(json.loads(original)["failure_code"], "executable_fingerprint")
            self.assertEqual(list(root.iterdir()), [root / "mgsvtpp.exe"])

    def test_single_file_app_is_deterministic_self_contained_and_read_only(self):
        import zipfile
        path = Path(__file__).resolve().parents[1] / "build-support/package_controller_check.py"
        spec = importlib.util.spec_from_file_location("controller_packager", path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "check.pyz"
            with mock.patch.object(builder, "OUTPUT", app), contextlib.redirect_stdout(io.StringIO()):
                builder.build()
                original = app.read_bytes()
                builder.build()
                self.assertEqual(original, app.read_bytes())
            with zipfile.ZipFile(app) as packaged:
                self.assertEqual(set(packaged.namelist()), {"__main__.py", "allocation_manifest.json", "THIRD_PARTY_NOTICES.txt",
                    "mgsv_pack_report.py", "plan_free_roam_allocation.py", "mgsv_fox2.py", "inspect_free_roam_controllers.py"})
            game = root / "copy"
            game.mkdir()
            (game / "mgsvtpp.exe").write_bytes(b"SYNTHETIC_WRONG_EXE")
            output = root / "result.json"
            # Run from another directory with an isolated Python sys.path.
            result = subprocess.run([sys.executable, "-I", str(app), "--game-dir", str(game), "--output", str(output)],
                                    cwd=directory, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["failure_code"], "executable_fingerprint")
            self.assertFalse(json.loads(output.read_text())["can_install"])
            self.assertEqual((game / "mgsvtpp.exe").read_bytes(), b"SYNTHETIC_WRONG_EXE")


if __name__ == "__main__":
    unittest.main()
