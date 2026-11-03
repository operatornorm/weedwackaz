#!/usr/bin/env python3
"""Development-only allocation identity preflight. Never installs or transforms assets.

Reads a metadata JSON, produces a non-applicable plan, and provides pure guards
for eventual live-byte verification and preservation checks. No game/Steam API.
"""

import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import sys

from mgsv_pack_report import MAX_PACK, get32, inspect, path_hash, require


MANIFEST = Path(__file__).resolve().parents[1] / "qa/free-roam-allocation-fingerprints.json"
MAX_PRESERVATION_BYTES = MAX_PACK
PREFIX = "/Assets/tpp/level_asset/chara/player/game_object/"
SHARED_PACK = "/Assets/tpp/pack/coop/coop_essentials.fpk"
FREE_ROAM_SUPPORT = "/Assets/tpp/pack/coop/coop_free_roam_support.fpk"
SHARED_MEMBERS = [PREFIX + name + ".fox2" for name in (
    "two_player2_instances", "player2_additional_parts_x1",
    "player2_online_motion", "player2_mtbs_motion_loader")]
ARCHIVES = {"master/0/00.dat", "master/0/00.dat.vendor", "master/0/01.dat", "master/data1.dat"}
ARCHIVES.update("master/chunk%d.dat" % i for i in range(5))


def staged_package_paths(target_id):
    require(isinstance(target_id, str) and re.fullmatch(r"[a-z0-9-]+", target_id), "staged_target_id")
    fpk = "/Assets/tpp/pack/coop/free/" + target_id + ".fpk"
    return fpk, fpk + "d"


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_field")
            result[key] = value
        return result

    with path.open("rb") as file:
        raw = file.read((16 << 20) + 1)
    require(len(raw) <= 16 << 20, "json_size_limit")
    return json.loads(raw, object_pairs_hook=pairs)


def asset_name(name):
    return isinstance(name, str) and len(name) <= 512 and bool(
        re.fullmatch(r"/Assets/[A-Za-z0-9_./-]+", name)) and posixpath.normpath(name) == name


def candidate(name):
    return name.startswith(PREFIX) and any(word in posixpath.basename(name) for word in ("instance", "parts"))


def validate_metadata(metadata, expected_hash, kind):
    require(isinstance(metadata, dict) and metadata.get("kind") == kind, "package_kind")
    require(metadata.get("container_sha256") == expected_hash, "package_fingerprint")
    members, references = metadata.get("members"), metadata.get("references")
    require(isinstance(members, list) and isinstance(references, list) and
            len(members) + len(references) <= 4096, "package_records")
    names = []
    for member in members:
        require(isinstance(member, dict) and asset_name(member.get("name")), "member_name")
        require(all(type(member.get(key)) is int and 0 <= member[key] <= MAX_PACK
                    for key in ("offset", "size")) and
                member["size"] <= MAX_PACK - member["offset"], "member_span")
        names.append(member["name"])
    require(len(names) == len(set(names)), "duplicate_member")
    require(all(asset_name(ref) for ref in references) and
            len(references) == len(set(references)), "package_references")
    return members


def validate_allocator(metadata, target):
    members = validate_metadata(metadata, target["package_sha256"], "fpkd")
    require(len(members) == target["member_count"], "package_member_count")
    require(not any(member["name"] in SHARED_MEMBERS for member in members), "replacement_already_present")
    matches = [member for member in members if candidate(member["name"])]
    require(len(matches) == 1 and matches[0]["name"] == target["member"], "allocator_cardinality")
    member = matches[0]
    require(member.get("stored_member_sha256") == target["member_sha256"] and
            member["size"] == target["member_size"], "allocator_fingerprint")
    return member


def build_plan(report, manifest):
    require(isinstance(report, dict) and manifest.get("schema") == 1, "report_or_manifest_schema")
    require(report.get("kind") == "mgsv_pack_metadata_only_not_gameplay_validation" and
            report.get("version") == "python-2", "report_schema")
    require(report.get("executable_sha256") == manifest["executable_sha256"], "executable_fingerprint")
    require(report.get("enumeration_finished") is True and
            all(type(report.get(key)) is int and report[key] == 0
                for key in ("limits_hit", "parse_failures", "containers_failed")), "partial_report")
    archives, containers = report.get("archives"), report.get("containers")
    require(isinstance(archives, list) and len(archives) == len(ARCHIVES) and
            all(isinstance(archive, dict) for archive in archives) and
            {archive.get("archive") for archive in archives} == ARCHIVES, "archive_set")
    require(all(archive.get("status") == "indexed" and type(archive.get("version")) is int and
                archive["version"] in (1, 2) and type(archive.get("entries")) is int and
                0 <= archive["entries"] <= 250000
                for archive in archives), "archive_not_indexed")
    require(isinstance(containers, list) and 0 < len(containers) <= 64 and
            type(report.get("containers_inspected")) is int and
            report["containers_inspected"] == len(containers) and
            all(isinstance(node, dict) and node.get("status") == "metadata_ok" for node in containers),
            "partial_containers")
    archive_counts = {archive["archive"]: archive["entries"] for archive in archives}
    probes = report.get("probes")
    require(isinstance(probes, list) and len(probes) <= 4096 and
            all(isinstance(probe, dict) for probe in probes), "probe_set")
    require(len(manifest["targets"]) == 3 and len({t["id"] for t in manifest["targets"]}) == 3,
            "target_set")
    operations = []
    for target in manifest["targets"]:
        for name, expected_hash, kind in (
                (target["loader_pack"], target["loader_pack_sha256"], "fpk"),
                (target["package"], target["package_sha256"], "fpkd")):
            matched_probes = [probe for probe in probes if probe.get("path") == name]
            require(len(matched_probes) == 1 and type(matched_probes[0].get("matches")) is int and
                    matched_probes[0]["matches"] == 1, "probe_occurrence_count")
            matches = [node for node in containers if node.get("path") == name]
            require(len(matches) == 1, "package_occurrence_count")
            node = matches[0]
            require(node.get("archive") == target["archive"] and type(node.get("depth")) is int and
                    node["depth"] == 0 and type(node.get("entry")) is int and
                    0 <= node["entry"] < archive_counts[target["archive"]] and
                    not node.get("parent") and node.get("hash") == "%016x" % path_hash(name), "package_source")
            require(sum(other.get("depth") == 0 and other.get("archive") == node["archive"] and
                        other.get("entry") == node["entry"] for other in containers) == 1,
                    "package_identity_alias")
            require(node.get("checksum_stage") in ("both", "decoded_payload", "decrypted_stored"),
                    "package_checksum_unverified")
            validate_metadata(node.get("metadata"), expected_hash, kind)
            if kind == "fpkd":
                member = validate_allocator(node["metadata"], target)
                operations.append({
                    "id": target["id"], "mission": target["mission"], "archive": target["archive"],
                    "package": name, "package_sha256": expected_hash,
                    "staged_loader_pack": staged_package_paths(target["id"])[0],
                    "staged_package": staged_package_paths(target["id"])[1],
                    "load_original_when_disabled": True,
                    "proposed_expand": {"name": member["name"], "size": member["size"],
                                        "sha256": target["member_sha256"],
                                        "parts_profile_hash": target["parts_profile_hash"], "parts_slots": 2},
                    "preserve_other_members": len(node["metadata"]["members"]) - 1,
                    "required_shared_pack": FREE_ROAM_SUPPORT,
                })
    return {
        "kind": "free_roam_allocation_identity_plan", "schema": 1, "can_apply": False,
        "executable_sha256": manifest["executable_sha256"], "operations": operations,
        "shared_support_members": list(SHARED_MEMBERS[1:]),
        "excluded_shared_controller": SHARED_MEMBERS[0],
        "unresolved_prerequisites": [
            "Recompute all fingerprints from live package bytes immediately before a staged transform.",
            "Bind the captured controller structure/profile to live bytes and recheck immediately before transformation.",
            "Verify two-player resource/profile compatibility and three-member support; exclude duplicate allocation.",
            "Implement lifecycle and automated real-client QA before enabling these missions.",
            "Require transactional staging/backups and preservation checks before any game-copy installation.",
        ],
        "excluded_from_this_plan": ["Mother Base", "battle hangar", "zoo", "ward"],
    }


def verify_live_package(data, target):
    """Pure identity guard for decoded FPKD bytes; NOT permission to install."""
    require(isinstance(data, bytes) and len(data) <= MAX_PACK, "package_size")
    require(hashlib.sha256(data).hexdigest() == target["package_sha256"], "package_fingerprint")
    metadata = inspect(data)
    validate_allocator(metadata, target)
    return metadata


def preservation_snapshot(data):
    """Internal guard data only; never exports asset bodies or decrypts members."""
    # Budget BEFORE inspect(), which also fingerprints named allocator members.
    require(isinstance(data, bytes) and 48 <= len(data) <= MAX_PACK, "package_size")
    count, refs = get32(data, 36), get32(data, 40)
    require(count + refs <= 4096 and 48 + count * 48 + refs * 16 <= len(data), "package_records")
    require(sum(get32(data, 48 + i * 48 + 8) for i in range(count)) <= MAX_PRESERVATION_BYTES,
            "preservation_hash_budget")
    metadata = inspect(data)
    validate_metadata(metadata, metadata["container_sha256"], "fpkd")
    entries = metadata["members"]
    return {
        "header_opaque": data[14:32].hex() + data[44:48].hex(),
        "members": [(member["name"], member["size"], hashlib.sha256(
            data[member["offset"]:member["offset"] + member["size"]]).hexdigest(),
                     b"".join(data[48 + i * 48 + start:48 + i * 48 + end]
                              for start, end in ((4, 8), (12, 16), (20, 24), (28, 48))).hex())
                    for i, member in enumerate(entries)],
        "references": [(name, data[48 + len(entries) * 48 + i * 16 + 4:
                                    48 + len(entries) * 48 + i * 16 + 8].hex() +
                         data[48 + len(entries) * 48 + i * 16 + 12:
                              48 + len(entries) * 48 + i * 16 + 16].hex())
                       for i, name in enumerate(metadata["references"])],
    }


def verify_preservation(before, after, removed_name):
    """Reject a future repack that changes anything except the single requested member."""
    old, new = preservation_snapshot(before), preservation_snapshot(after)
    require(sum(name == removed_name for name, *_ in old["members"]) == 1, "removal_cardinality")
    require([entry for entry in old["members"] if entry[0] != removed_name] == new["members"] and
            old["references"] == new["references"] and
            old["header_opaque"] == new["header_opaque"], "unrelated_members_changed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        plan = build_plan(read_json(args.report), read_json(MANIFEST))
        with args.output.open("x", encoding="utf-8") as file:
            json.dump(plan, file, indent=2)
            file.write("\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Preflight rejected input or output; no game files were accessed.", file=sys.stderr)
        return 1
    print("Identity plan written; can_apply=false. No game files were accessed or transformed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
