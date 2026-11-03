"""Check a bounded game-copy receipt; no launch or gameplay authority is granted."""
import argparse
import json
import re
from pathlib import Path

PATHS = frozenset(("mgsvtpp.exe", "steam_api64.dll", "master/0/00.dat", "master/0/01.dat",
                   "master/chunk0.dat", "master/chunk1.dat", "master/chunk2.dat",
                   "master/chunk3.dat", "master/chunk4.dat", "master/data1.dat"))
PINS = {"mgsvtpp.exe": "f3818d172293800171a344a71957bc7257f591bbf7c1792e10fef6bfbba7f4f2",
        "steam_api64.dll": "08bd0152356e5619ee56a6714ac951b6800dbb21821693a4efaf85278442c60a"}
BASE_KEYS = {"schema", "stage", "run", "session", "challenge", "source_tag", "files"}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > 8192:
        raise ValueError("oversized report")
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)


def files(value):
    if not isinstance(value, list) or len(value) != len(PATHS):
        raise ValueError("wrong file count")
    result = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise ValueError("invalid file schema")
        name = item["path"]
        if not isinstance(name, str) or name not in PATHS or name in result:
            raise ValueError("unknown or duplicate file")
        if type(item["bytes"]) is not int or not 0 < item["bytes"] <= 8 * 1024**3:
            raise ValueError("invalid file size")
        if not isinstance(item["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", item["sha256"]):
            raise ValueError("invalid digest")
        if name in PINS and item["sha256"] != PINS[name]:
            raise ValueError("wrong pinned binary")
        result[name] = (item["bytes"], item["sha256"])
    return result


def check(manifest_raw, report_raw, offline, published_source_tag):
    manifest, report = decode(manifest_raw), decode(report_raw)
    if not isinstance(manifest, dict) or set(manifest) != BASE_KEYS or not isinstance(report, dict) or set(report) != BASE_KEYS | {"result"}:
        raise ValueError("invalid receipt schema")
    for value in (manifest, report):
        if type(value["schema"]) is not int or value["schema"] != 1 or value["stage"] != "game-stage-v1":
            raise ValueError("wrong receipt phase")
        for key, size in (("run", 32), ("session", 32), ("challenge", 32), ("source_tag", 64)):
            if not isinstance(value[key], str) or not re.fullmatch("[0-9a-f]{" + str(size) + "}", value[key]) or value[key] == "0" * size:
                raise ValueError("invalid receipt identifier")
    if offline.get("result") != "local_network_cut_observations_accepted" or manifest["run"] != offline.get("run_id") or manifest["session"] != offline.get("guest_session_id"):
        raise ValueError("wrong offline guest session")
    if manifest["source_tag"] != published_source_tag or report["result"] != "files_copied_not_launched":
        raise ValueError("wrong source or result")
    if any(manifest[key] != report[key] for key in BASE_KEYS - {"files"}):
        raise ValueError("mismatched staging request")
    copied = files(manifest["files"])
    if copied != files(report["files"]):
        raise ValueError("file copy mismatch")
    return {"schema": 1, "result": "copy_observations_accepted", "run_id": manifest["run"],
            "guest_session_id": manifest["session"], "challenge": manifest["challenge"],
            "files": len(copied), "bytes": sum(size for size, digest in copied.values()),
            "executed_source_attested": False, "all_archives_stock_verified": False,
            "save_isolation_verified": False, "offline_license_verified": False,
            "game_launched": False, "launch_authorized": False, "co_op_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "report", "offline"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--source-tag", required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.manifest.read_bytes(), args.report.read_bytes(),
                           json.loads(args.offline.read_text()), args.source_tag), indent=2))


if __name__ == "__main__":
    main()
