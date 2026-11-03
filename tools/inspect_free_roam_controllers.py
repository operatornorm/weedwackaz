#!/usr/bin/env python3
"""Read only three pinned Free Roam controller structures; export metadata only."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zlib

import mgsv_fox2
import mgsv_pack_report as qar
from plan_free_roam_allocation import ARCHIVES, MANIFEST, read_json, verify_live_package, verify_preservation


def transform_verified_package(data, target):
    """Pure, development-only transform. No CLI exposes application/installation.

    Remove one table row, retaining all names/bodies/offsets and references.
    The removed member's bytes remain unreachable padding. No asset is executed.
    """
    metadata = verify_live_package(data, target)
    selected = next(i for i, m in enumerate(metadata["members"]) if m["name"] == target["member"])
    member = metadata["members"][selected]
    fox = data[member["offset"]:member["offset"] + member["size"]]
    mgsv_fox2.validate_single_slot(mgsv_fox2.parse_fox2(fox))
    count, refs = qar.get32(data, 36), qar.get32(data, 40)
    table_end, at = 48 + count * 48 + refs * 16, 48 + selected * 48
    output = bytearray(data)
    output[at:table_end - 48] = data[at + 48:table_end]
    output[table_end - 48:table_end] = bytes(48)
    struct.pack_into("<I", output, 36, count - 1)
    output = bytes(output)
    verify_preservation(data, output, target["member"])
    return output


def collect(root, manifest):
    result = {"kind": "mgsv_controller_structure_only_not_gameplay_validation", "version": 1,
              "read_only": True, "can_install": False, "archives": [], "controllers": [],
              "limitations": ["No assets, scripts, saves, Steam accounts or PC paths exported.",
                              "Parts slots and entity graphs do not prove realized player count or working co-op.",
                              "No package transforms or game-file changes are performed by this command."]}
    digest, count = hashlib.sha256(), 0
    with (root / "mgsvtpp.exe").open("rb") as executable:
        for block in iter(lambda: executable.read(1 << 20), b""):
            count += len(block)
            qar.require(count <= 512 << 20, "executable_size_limit")
            digest.update(block)
    result["executable_sha256"] = digest.hexdigest()
    qar.require(count > 0, "executable_empty")
    if result["executable_sha256"] != manifest["executable_sha256"]:
        result["failure_code"] = "executable_fingerprint"
        return result
    sources, index, total_entries, total_decoded = [], {}, 0, 0
    wanted = {qar.path_hash(target[key]) for target in manifest["targets"] for key in ("loader_pack", "package")}
    try:
        for archive in sorted(ARCHIVES):
            info = {"archive": archive, "status": "missing_or_unreadable"}
            result["archives"].append(info)
            file = None
            try:
                path = root / archive
                qar.require(not path.is_symlink() and path.is_file(), "archive_missing_or_nonregular")
                file = path.open("rb")
                size = os.fstat(file.fileno()).st_size
                version, entries = qar.index_archive(file, size)
                total_entries += len(entries)
                qar.require(total_entries <= 1000000, "total_entry_limit")
                source = (file, size, version, archive)
                sources.append(source)
                info.update(status="indexed", entries=len(entries), version=version)
                for entry in entries:
                    if entry[0] in wanted:
                        index.setdefault(entry[0], []).append((source, entry))
            except (OSError, ValueError, struct.error) as error:
                if file:
                    file.close()
                info.update(status="archive_check_failed", failure_code=qar.failure_code(error))
        result["archive_index_complete"] = all(a["status"] == "indexed" for a in result["archives"])
        for target in manifest["targets"]:
            node = {"id": target["id"], "archive": target["archive"], "package": target["package"],
                    "member": target["member"], "status": "checking"}
            result["controllers"].append(node)
            try:
                qar.require(result["archive_index_complete"], "archive_index_incomplete")
                packages = {}
                for key, hash_key in (("loader_pack", "loader_pack_sha256"), ("package", "package_sha256")):
                    matches = index.get(qar.path_hash(target[key]), [])
                    qar.require(len(matches) == 1, "package_occurrence_count")
                    source, entry = matches[0]
                    file, size, version, archive = source
                    qar.require(archive == target["archive"], "package_source")
                    qar.require(total_decoded + entry[3] <= qar.MAX_TOTAL, "total_decode_limit")
                    data = qar.decode(file, size, version, entry)
                    total_decoded += len(data)
                    qar.require(hashlib.sha256(data).hexdigest() == target[hash_key], "package_fingerprint")
                    packages[key] = data
                data = packages["package"]
                metadata = verify_live_package(data, target)
                member = next(m for m in metadata["members"] if m["name"] == target["member"])
                body = data[member["offset"]:member["offset"] + member["size"]]
                node["member_sha256"] = hashlib.sha256(body).hexdigest()
                tree = mgsv_fox2.parse_fox2(body)
                node["structure"] = mgsv_fox2.controller_summary(tree)
                mgsv_fox2.validate_single_slot(tree)
                node["status"] = "structure_matches_policy"
            except (OSError, ValueError, struct.error, zlib.error) as error:
                node.update(status="requires_review", failure_code=qar.failure_code(error))
        result["structures_matching_policy"] = sum(n["status"] == "structure_matches_policy" for n in result["controllers"])
        result["structures_requiring_review"] = len(result["controllers"]) - result["structures_matching_policy"]
        return result
    finally:
        for file, *_ in sources:
            file.close()


def main(argv=None, manifest=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root, parent = args.game_dir.resolve(strict=True), args.output.parent.resolve(strict=True)
        qar.require(root != parent and root not in parent.parents, "output_must_be_outside_game_copy")
        qar.require(not args.output.exists(), "output_already_exists")
        result = collect(root, manifest if manifest is not None else read_json(MANIFEST))
        data = json.dumps(result, indent=2).encode() + b"\n"
        qar.require(len(data) <= 1 << 20, "output_size_limit")
        with (parent / args.output.name).open("xb") as output:
            output.write(data)
    except (OSError, ValueError, KeyError, struct.error):
        print("Controller check failed; check the copied-game directory and a new output filename.", file=sys.stderr)
        return 1
    print("Controller metadata written. No game files were changed or transformed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
