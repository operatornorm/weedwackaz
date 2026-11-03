"""Profile-preserving prototype checks; no owner package bytes or game clients."""

import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import expand_free_roam_allocation as expansion
import mgsv_fox2 as fox
import mgsv_pack_report as qar
import plan_free_roam_allocation as identity
import inspect_free_roam_controllers as check
from test_controller_preflight import copied_game, FIXTURES
from test_free_roam_allocation import pack


PROFILES = {"Normal": "0000bc3759d825c8", "NormalScarf": "0000c94e97c2d50c"}


def body(name):
    return (FIXTURES / ("synthetic_profile_" + name + ".fox2")).read_bytes()


def target_for(data, member, fox_body, profile):
    return {"member": member, "member_count": 3, "member_size": len(fox_body),
            "member_sha256": hashlib.sha256(fox_body).hexdigest(),
            "package_sha256": hashlib.sha256(data).hexdigest(), "parts_profile_hash": profile}


def add_literal(data, key, text):
    tree = fox.parse_fox2(data)
    data = bytearray(data[:tree["literal_end"]])
    encoded = text.encode()
    data.extend(struct.pack("<Qi", key, len(encoded)) + encoded + bytes(8))
    data.extend(bytes((-len(data)) % 16) + b"\0\0end")
    data.extend(bytes((-len(data)) % 16))
    return bytes(data)


class AllocationExpansionTests(unittest.TestCase):
    def test_both_profiles_expand_without_substituting_the_original_type(self):
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                original = body(name)
                output = expansion.expand_controller(original, profile)
                self.assertEqual(output, expansion.expand_controller(original, profile))
                expansion.verify_controller_expansion(original, output, profile)
                tree = fox.parse_fox2(output)
                e = expansion.controller(tree)
                for array in expansion.ARRAYS:
                    self.assertEqual(fox.prop(e, array, 11, 1, 2)["values"], [int(profile, 16)] * 2)
                self.assertIn(fox.strcode64(expansion.SINGLE_PACKAGE), tree["literals"])
                self.assertEqual(tree["literals"][fox.strcode64(expansion.TWO_PACKAGE)], expansion.TWO_PACKAGE)
                with self.assertRaises(ValueError): expansion.expand_controller(output, profile)

    def test_swapped_profiles_bad_scalar_values_and_nonzero_padding_are_rejected(self):
        original = body("NormalScarf")
        with self.assertRaises(ValueError): expansion.expand_controller(original, PROFILES["Normal"])
        tree = fox.parse_fox2(original)
        e = expansion.controller(tree)
        ordinary_after = expansion.expand_controller(original, PROFILES["NormalScarf"])
        at = fox.prop(e, "instanceSettings_instanceBlockSize", 5, 0, 1)["offset"]
        bad = bytearray(original)
        struct.pack_into("<I", bad, at + 32, 563199)
        with self.assertRaises(ValueError): expansion.expand_controller(bytes(bad), PROFILES["NormalScarf"])
        for array in expansion.ARRAYS:
            at = fox.prop(e, array, 11, 1, 1)["offset"]
            bad = bytearray(original)
            bad[at + 40] = 1
            with self.assertRaises(ValueError): expansion.expand_controller(bytes(bad), PROFILES["NormalScarf"])
            with self.assertRaisesRegex(ValueError, "expansion_array_padding"):
                expansion.verify_controller_expansion(bytes(bad), ordinary_after, PROFILES["NormalScarf"])
        at = fox.prop(e, expansion.ARRAYS[1], 11, 1, 1)["offset"]
        bad = bytearray(original)
        struct.pack_into("<Q", bad, at + 32, int(PROFILES["Normal"], 16))
        with self.assertRaises(ValueError): expansion.expand_controller(bytes(bad), PROFILES["NormalScarf"])

    def test_existing_correct_literal_is_reused_without_duplicate_records(self):
        original = add_literal(body("Normal"), fox.strcode64(expansion.TWO_PACKAGE), expansion.TWO_PACKAGE)
        old = fox.parse_fox2(original)
        output = expansion.expand_controller(original, PROFILES["Normal"])
        new = fox.parse_fox2(output)
        self.assertEqual(old["literal_records"], new["literal_records"])
        self.assertEqual(len(original), len(output))
        expansion.verify_controller_expansion(original, output, PROFILES["Normal"])

    def test_fox_byte_allowlist_and_exact_literal_extension_reject_extra_changes(self):
        original = body("Normal")
        output = expansion.expand_controller(original, PROFILES["Normal"])
        changed = bytearray(output)
        # Changing an entity ID may leave a valid graph, but is outside the five-property edit.
        struct.pack_into("<Q", changed, fox.parse_fox2(output)["entities"][2]["offset"] + 18, 99)
        with self.assertRaises(ValueError): expansion.verify_controller_expansion(original, bytes(changed), PROFILES["Normal"])
        extra = add_literal(output, fox.strcode64("DefaultCommonMotion"), "DefaultCommonMotion")
        fox.parse_fox2(extra)  # Valid format and same resolved map, but unauthorized extra record.
        with self.assertRaises(ValueError): expansion.verify_controller_expansion(original, extra, PROFILES["Normal"])

    def test_package_append_preserves_all_other_bytes_in_first_middle_and_last_rows(self):
        member = "/Assets/tpp/level_asset/chara/player/game_object/single_player2_instance.fox2"
        for profile_name, profile in PROFILES.items():
            for position in range(3):
                with self.subTest(profile=profile_name, row=position):
                    fox_body = body(profile_name)
                    entries = [("/Assets/test/a.bin", b"UNKNOWN_A"), ("/Assets/test/b.bin", b"UNKNOWN_B")]
                    entries.insert(position, (member, fox_body))
                    data = pack(entries, ["/Assets/test/first.fpk", "/Assets/test/second.fpk"])
                    target = target_for(data, member, fox_body, profile)
                    output = expansion.expand_package(data, target)
                    self.assertEqual(data, pack(entries, ["/Assets/test/first.fpk", "/Assets/test/second.fpk"]))
                    expansion.verify_package_expansion(data, output, target)
                    old, new = qar.inspect(data), qar.inspect(output)
                    self.assertEqual([m["name"] for m in old["members"]], [m["name"] for m in new["members"]])
                    self.assertEqual(old["references"], new["references"])
                    self.assertEqual(new["members"][position]["offset"], fox.align16(len(data)))
                    with self.assertRaises(ValueError): expansion.expand_package(output, target)
                    wrong = dict(target, parts_profile_hash=PROFILES["Normal" if profile_name == "NormalScarf" else "NormalScarf"])
                    with self.assertRaises(ValueError): expansion.expand_package(data, wrong)

    def test_package_verification_rejects_unrelated_mutation_and_size_overflow(self):
        member = "/Assets/tpp/level_asset/chara/player/game_object/single_player2_instance.fox2"
        fox_body = body("Normal")
        data = pack([("/Assets/test/a.bin", b"KEEP_A"), (member, fox_body), ("/Assets/test/b.bin", b"KEEP_B")])
        target = target_for(data, member, fox_body, PROFILES["Normal"])
        output = expansion.expand_package(data, target)
        for at in (14, 48 + 32, qar.inspect(output)["members"][0]["offset"]):
            bad = bytearray(output)
            bad[at] ^= 1
            with self.assertRaises(ValueError): expansion.verify_package_expansion(data, bytes(bad), target)
        with mock.patch.object(expansion, "MAX_PACK", len(data) + 1):
            with self.assertRaisesRegex(ValueError, "expansion_package_size_limit"): expansion.expand_package(data, target)
        with mock.patch.object(fox, "MAX_FOX", len(fox_body) + 1):
            with self.assertRaises(ValueError): expansion.expand_controller(fox_body, PROFILES["Normal"])

    def test_literal_record_limit_is_checked_before_appending(self):
        original = body("Normal")
        tree = fox.parse_fox2(original)
        raw = bytearray(original[:tree["literal_end"]])
        raw.extend(struct.pack("<Qi", fox.strcode64(""), 0) * (4095 - tree["literal_records"]))
        raw.extend(bytes(8))
        raw.extend(bytes((-len(raw)) % 16) + b"\0\0end")
        raw.extend(bytes((-len(raw)) % 16))
        self.assertEqual(fox.parse_fox2(bytes(raw))["literal_records"], 4095)
        with self.assertRaisesRegex(ValueError, "expansion_literal_limit"):
            expansion.expand_controller(bytes(raw), PROFILES["Normal"])

    def test_three_member_support_preserves_story_essentials_and_has_no_allocator(self):
        source = Path(os.environ.get("DYNAMITE_SOURCE_DIR", str(Path(__file__).resolve().parents[2] / "dynamite")))
        original = (source / "moddata/coop_essentials/coop_essentials.fpkd").read_bytes()
        manifest = identity.read_json(identity.MANIFEST)
        result = expansion.make_support_pack(original, manifest["support_source_sha256"])
        identity.verify_preservation(original, result, identity.SHARED_MEMBERS[0])
        self.assertEqual([m["name"] for m in qar.inspect(result)["members"]], identity.SHARED_MEMBERS[1:])
        self.assertEqual(hashlib.sha256(original).hexdigest(), manifest["support_source_sha256"])
        entries = []
        for member in qar.inspect(original)["members"]:
            entries.append((member["name"], original[member["offset"]:member["offset"] + member["size"]]))
        # A malformed support file hiding another allocator under the parts name must fail.
        entries[1] = (entries[1][0], entries[0][1])
        bad = pack(entries)
        with self.assertRaisesRegex(ValueError, "support_duplicate_allocator"):
            expansion.make_support_pack(bad, hashlib.sha256(bad).hexdigest())

    def test_report_validation_binds_profiles_identity_and_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = copied_game(root, matching_profiles=True)
            report = check.collect(root, manifest)
            result = expansion.validate_controller_report(report, manifest)
            self.assertEqual(result["structures_confirmed"], 3)
            self.assertFalse(result["can_install"])
            self.assertFalse(result["profile_compatibility_verified"])
            for kind in ("member", "profile", "counter", "boolean", "archive", "extra_property"):
                bad = copy.deepcopy(report)
                if kind == "member": bad["controllers"][0]["member_sha256"] = "0" * 64
                elif kind == "profile": bad["controllers"][0]["structure"]["selected_fields"][expansion.ARRAYS[0]]["value_hashes"] = [PROFILES["Normal"]]
                elif kind == "counter": bad["structures_requiring_review"] = 1
                elif kind == "boolean": bad["controllers"][0]["structure"]["selected_fields"]["name"]["count"] = True
                elif kind == "archive": bad["archives"].pop()
                else: bad["controllers"][0]["structure"]["unexpected_property_hashes"] = ["bad"]
                with self.subTest(kind=kind):
                    with self.assertRaises(ValueError): expansion.validate_controller_report(bad, manifest)


if __name__ == "__main__":
    unittest.main()
