"""Pure development prototype: expand a verified controller while retaining its profile.

No CLI, game-file writer, installer or runtime activation. Actual resource/profile
compatibility still requires verification on game clients.
"""

import hashlib
import struct

import mgsv_fox2 as fox
from mgsv_pack_report import MAX_PACK, get32, inspect, require
from plan_free_roam_allocation import SHARED_MEMBERS, preservation_snapshot, verify_live_package, verify_preservation
from plan_free_roam_allocation import ARCHIVES


SINGLE_PACKAGE = "/Assets/tpp/pack/player/game_object/single_player_game_obj.fpk"
TWO_PACKAGE = "/Assets/tpp/pack/player/game_object/two_players_game_obj.fpk"
STOCK_NUMERIC = {
    "configuration_commonMotionBlockSize": 13631488,
    "configuration_commonMotionBlockSizePs3": 10485760,
    "configuration_additiveMotionBlockCount": 1,
    "configuration_additiveMotionBlockSize": 3145728,
    "configuration_partsBlockCount": 1,
    "configuration_partsBlockSize": 2097152,
    "instanceSettings_instanceBlockSize": 563200,
}
ARRAYS = ("instanceSettings_partsTypeNames", "instanceSettings_partsTypeInitial")
CHANGED = {"configuration_partsBlockCount", "instanceSettings_instanceBlockSize",
           "instanceSettings_instancePackagePath", *ARRAYS}
KNOWN_PROFILES = {"0000c94e97c2d50c", "0000bc3759d825c8"}


def controller(tree):
    matches = [e for e in tree["entities"] if e["class_hash"] == fox.strcode64(fox.CONTROLLER)]
    require(len(matches) == 1, "expansion_controller_count")
    return matches[0]


def verify_profile(tree, profile, slots):
    require(profile in KNOWN_PROFILES, "expansion_profile_unknown")
    fox.validate_controller_slots(tree, slots)
    e = controller(tree)
    for name, stock in STOCK_NUMERIC.items():
        expected = stock * slots if name in ("configuration_partsBlockCount", "instanceSettings_instanceBlockSize") else stock
        require(fox.prop(e, name, 5, 0, 1)["values"] == [expected], "expansion_numeric_precondition")
    for name in ARRAYS:
        require(fox.prop(e, name, 11, 1, slots)["values"] == [int(profile, 16)] * slots, "expansion_profile_precondition")
    require(fox.prop(e, "instanceSettings_commonMotionTypeName", 11, 0, 1)["values"] ==
            [fox.strcode64("DefaultCommonMotion")], "expansion_motion_precondition")
    expected_path = SINGLE_PACKAGE if slots == 1 else TWO_PACKAGE
    require(fox.prop(e, "instanceSettings_instancePackagePath", 11, 0, 1)["values"] ==
            [fox.strcode64(expected_path)] and fox.literal(tree, fox.strcode64(expected_path)) == expected_path,
            "expansion_instance_precondition")


def expansion_spans(tree):
    e = controller(tree)
    spans = []
    for name in ("configuration_partsBlockCount", "instanceSettings_instanceBlockSize"):
        at = fox.prop(e, name, 5, 0, 1)["offset"]
        spans.append((at + 32, at + 36))
    at = fox.prop(e, "instanceSettings_instancePackagePath", 11, 0, 1)["offset"]
    spans.append((at + 32, at + 40))
    for name in ARRAYS:
        at = fox.prop(e, name, 11, 1)["offset"]
        spans.extend(((at + 10, at + 12), (at + 40, at + 48)))
    return spans


def verify_source_padding(data, tree):
    for name in ARRAYS:
        p = fox.prop(controller(tree), name, 11, 1, 1)
        require(p["size"] == 48 and data[p["offset"] + 40:p["offset"] + 48] == bytes(8),
                "expansion_array_padding")


def verify_controller_expansion(before, after, profile):
    old, new = fox.parse_fox2(before), fox.parse_fox2(after)
    verify_profile(old, profile, 1)
    verify_source_padding(before, old)
    verify_profile(new, profile, 2)
    require(old["strings_at"] == new["strings_at"] and len(old["entities"]) == len(new["entities"]), "expansion_layout_changed")
    prefix_old, prefix_new = bytearray(before[:old["strings_at"]]), bytearray(after[:new["strings_at"]])
    for start, end in expansion_spans(old):
        prefix_old[start:end] = prefix_new[start:end] = bytes(end - start)
    require(prefix_old == prefix_new, "expansion_unrelated_bytes_changed")
    for e_old, e_new in zip(old["entities"], new["entities"]):
        require({k: v for k, v in e_old.items() if k != "properties"} ==
                {k: v for k, v in e_new.items() if k != "properties"}, "expansion_entity_graph_changed")
        require(len(e_old["properties"]) == len(e_new["properties"]), "expansion_property_count_changed")
        for p_old, p_new in zip(e_old["properties"], e_new["properties"]):
            changed = e_old["class_hash"] == fox.strcode64(fox.CONTROLLER) and p_old["name_hash"] in {fox.strcode64(n) for n in CHANGED}
            require((p_old == p_new) if not changed else
                    ({k: v for k, v in p_old.items() if k != "values"} ==
                     {k: v for k, v in p_new.items() if k != "values"}), "expansion_unrelated_property_changed")
    expected_literals = dict(old["literals"])
    expected_literals[fox.strcode64(TWO_PACKAGE)] = TWO_PACKAGE
    extension = b""
    if fox.strcode64(TWO_PACKAGE) not in old["literals"]:
        encoded = TWO_PACKAGE.encode()
        extension = struct.pack("<Qi", fox.strcode64(TWO_PACKAGE), len(encoded)) + encoded
    require(new["literals"] == expected_literals and
            new["literal_end"] == old["literal_end"] + len(extension) and
            new["literal_records"] == old["literal_records"] + bool(extension) and
            before[old["strings_at"]:old["literal_end"]] == after[new["strings_at"]:old["literal_end"]] and
            after[old["literal_end"]:new["literal_end"]] == extension,
            "expansion_unrelated_literals_changed")


def expand_controller(data, profile):
    old = fox.parse_fox2(data)
    verify_profile(old, profile, 1)
    verify_source_padding(data, old)
    e, output = controller(old), bytearray(data[:old["literal_end"]])
    for name, expected in (("configuration_partsBlockCount", 2), ("instanceSettings_instanceBlockSize", 1126400)):
        struct.pack_into("<I", output, fox.prop(e, name, 5, 0, 1)["offset"] + 32, expected)
    struct.pack_into("<Q", output, fox.prop(e, "instanceSettings_instancePackagePath", 11, 0, 1)["offset"] + 32,
                     fox.strcode64(TWO_PACKAGE))
    for name in ARRAYS:
        p = fox.prop(e, name, 11, 1, 1)
        struct.pack_into("<h", output, p["offset"] + 10, 2)
        struct.pack_into("<Q", output, p["offset"] + 40, p["values"][0])
    key = fox.strcode64(TWO_PACKAGE)
    if key not in old["literals"]:
        require(old["literal_records"] < 4095, "expansion_literal_limit")
        encoded = TWO_PACKAGE.encode()
        output.extend(struct.pack("<Qi", key, len(encoded)) + encoded)
    else:
        require(old["literals"][key] == TWO_PACKAGE, "expansion_literal_conflict")
    output.extend(bytes(8))
    output.extend(bytes((-len(output)) % 16))
    output.extend(b"\0\0end")
    output.extend(bytes((-len(output)) % 16))
    require(len(output) <= fox.MAX_FOX, "expansion_size_limit")
    result = bytes(output)
    verify_controller_expansion(data, result, profile)
    return result


def expand_package(data, target):
    """Copy out a profile-preserving package. Never writes to disk or enables missions."""
    metadata = verify_live_package(data, target)
    index = next(i for i, member in enumerate(metadata["members"]) if member["name"] == target["member"])
    member = metadata["members"][index]
    body = data[member["offset"]:member["offset"] + member["size"]]
    expanded = expand_controller(body, target["parts_profile_hash"])
    offset = fox.align16(len(data))
    require(offset + len(expanded) <= MAX_PACK, "expansion_package_size_limit")
    output = bytearray(data + bytes(offset - len(data)) + expanded)
    row = 48 + index * 48
    struct.pack_into("<I", output, 10, len(output))
    struct.pack_into("<I", output, row, offset)
    struct.pack_into("<I", output, row + 8, len(expanded))
    result = bytes(output)
    verify_package_expansion(data, result, target)
    return result


def verify_package_expansion(before, after, target):
    metadata = verify_live_package(before, target)
    index = next(i for i, member in enumerate(metadata["members"]) if member["name"] == target["member"])
    old, new = preservation_snapshot(before), preservation_snapshot(after)
    require(len(old["members"]) == len(new["members"]) and old["references"] == new["references"] and
            old["header_opaque"] == new["header_opaque"], "expansion_package_metadata_changed")
    require(all(a == b for i, (a, b) in enumerate(zip(old["members"], new["members"])) if i != index) and
            old["members"][index][0] == new["members"][index][0] and
            old["members"][index][3] == new["members"][index][3], "expansion_unrelated_member_changed")
    prefix_old, prefix_new = bytearray(before), bytearray(after[:len(before)])
    row = 48 + index * 48
    for start, end in ((10, 14), (row, row + 4), (row + 8, row + 12)):
        prefix_old[start:end] = prefix_new[start:end] = bytes(end - start)
    require(prefix_old == prefix_new, "expansion_package_prefix_changed")
    offset, size = get32(after, row), get32(after, row + 8)
    require(offset == fox.align16(len(before)) and offset + size == len(after) and
            not any(after[len(before):offset]), "expansion_package_append_layout")
    old_member = metadata["members"][index]
    verify_controller_expansion(before[old_member["offset"]:old_member["offset"] + old_member["size"]],
                                after[offset:offset + size], target["parts_profile_hash"])


def make_support_pack(data, expected_sha256):
    """Derive three unchanged support members; retain existing story essentials untouched."""
    require(isinstance(data, bytes) and len(data) <= MAX_PACK and
            hashlib.sha256(data).hexdigest() == expected_sha256, "support_source_fingerprint")
    require(len(data) >= 48 and get32(data, 36) == 4 and get32(data, 40) == 0, "support_source_members")
    metadata = inspect(data)
    require(metadata["kind"] == "fpkd" and [m["name"] for m in metadata["members"]] == SHARED_MEMBERS and
            not metadata["references"], "support_source_members")
    removed = SHARED_MEMBERS[0]
    count, refs = get32(data, 36), get32(data, 40)
    end = 48 + count * 48 + refs * 16
    output = bytearray(data)
    output[48:end - 48] = data[96:end]
    output[end - 48:end] = bytes(48)
    struct.pack_into("<I", output, 36, count - 1)
    result = bytes(output)
    verify_preservation(data, result, removed)
    for member in inspect(result)["members"]:
        tree = fox.parse_fox2(result[member["offset"]:member["offset"] + member["size"]])
        require(all(e["class_hash"] != fox.strcode64(fox.CONTROLLER) for e in tree["entities"]), "support_duplicate_allocator")
    return result


def validate_controller_report(report, manifest):
    """Accept capture evidence without authorizing package application or runtime use."""
    require(report.get("kind") == "mgsv_controller_structure_only_not_gameplay_validation" and
            type(report.get("version")) is int and report["version"] == 1 and
            report.get("read_only") is True and report.get("can_install") is False,
            "controller_report_schema")
    require(report.get("executable_sha256") == manifest["executable_sha256"] and
            report.get("archive_index_complete") is True and
            type(report.get("structures_matching_policy")) is int and report["structures_matching_policy"] == 3 and
            type(report.get("structures_requiring_review")) is int and report["structures_requiring_review"] == 0,
            "controller_report_incomplete")
    archives, nodes = report.get("archives"), report.get("controllers")
    require(isinstance(archives, list) and len(archives) == len(ARCHIVES) and
            {a.get("archive") for a in archives} == ARCHIVES and
            all(a.get("status") == "indexed" for a in archives), "controller_report_archives")
    require(isinstance(nodes, list) and len(nodes) == 3 and
            {n.get("id") for n in nodes} == {t["id"] for t in manifest["targets"]}, "controller_report_targets")
    for target in manifest["targets"]:
        node = next(n for n in nodes if n["id"] == target["id"])
        require(node.get("status") == "structure_matches_policy" and
                all(node.get(key) == target[key] for key in ("archive", "package", "member", "member_sha256")),
                "controller_report_identity")
        shape = node.get("structure", {})
        require(shape.get("entity_classes") == [fox.DATASET, fox.CONTROLLER, fox.TEXTURE] and
                all(type(shape.get(key)) is int for key in ("entity_count", "controller_count", "controller_class_version")) and
                shape.get("entity_count") == 3 and shape.get("controller_count") == 1 and
                shape.get("controller_class_version") == 3 and shape.get("unexpected_property_hashes") == [],
                "controller_report_shape")
        fields = shape.get("selected_fields", {})
        require(set(fields) == set(fox.BLOCK_PROPERTIES), "controller_report_fields")
        for name in fox.BLOCK_PROPERTIES:
            p = fields[name]
            dtype = 5 if name in STOCK_NUMERIC else 21 if name == "dataSet" else 11
            require(all(type(p.get(key)) is int for key in ("datatype", "container", "count")) and
                    p.get("datatype") == dtype and p.get("container") == (1 if name in ARRAYS else 0) and
                    p.get("count") == 1, "controller_report_property_type")
            if name in STOCK_NUMERIC:
                require(p.get("values") == [STOCK_NUMERIC[name]] and type(p["values"][0]) is int,
                        "controller_report_numeric")
            if name in ARRAYS:
                require(p.get("value_hashes") == [target["parts_profile_hash"]], "controller_report_profile")
        require(fields["instanceSettings_instancePackagePath"].get("asset_paths") == [SINGLE_PACKAGE] and
                fields["instanceSettings_instancePackagePath"].get("value_hashes") == ["%016x" % fox.strcode64(SINGLE_PACKAGE)] and
                fields["instanceSettings_commonMotionTypeName"].get("value_hashes") == ["%016x" % fox.strcode64("DefaultCommonMotion")],
                "controller_report_instance")
    return {"structures_confirmed": 3, "can_install": False,
            "profile_compatibility_verified": False, "runtime_validated": False}
