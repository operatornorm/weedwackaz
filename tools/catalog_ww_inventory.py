#!/usr/bin/env python3
"""Normalize captured quest metadata as data; never infer gameplay compatibility.

Keep captures and generated catalogs in ignored private storage. Input strings
are never executed, imported, used as output paths, or treated as instructions.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

LOCATION_NAMES = {10: "Afghanistan", 20: "Africa", 50: "Mother Base"}
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")


def catalog(data):
    if len(data) > 512 * 1024:
        raise ValueError("Report exceeds the collector's size limit")
    rows = {}
    for line in data.decode("utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or not fields[0] or fields[0] in rows:
            raise ValueError("Malformed row or duplicate report key")
        rows[fields[0]] = fields[1]
    required = {"report.kind": "runtime_metadata_only_not_a_gameplay_test",
                "report.schema": "1", "report.complete": "true",
                "report.truncated": "false"}
    if any(rows.get(key) != value for key, value in required.items()):
        raise ValueError("A complete, non-truncated schema-1 metadata report is required")

    def integer(key):
        value = rows.get(key, "")
        if not re.fullmatch(r"[0-9]{1,9}", value):
            raise ValueError("Missing or invalid numeric registry field")
        return int(value)

    def optional_bool(key):
        value = rows.get(key)
        if value is None:
            return None
        if value not in ("true", "false"):
            raise ValueError("Invalid quest flag")
        return value == "true"

    group_ids = sorted({int(match[1]) for key in rows
                        if (match := re.fullmatch(r"quests\.questList\.(\d+)\.locationId", key))})
    if integer("quests.questList.recorded_keys") != len(group_ids):
        raise ValueError("Quest group count does not match the report")
    groups, quests = [], []
    for group_id in group_ids:
        prefix = "quests.questList.%d." % group_id
        location = integer(prefix + "locationId")
        item_ids = sorted({int(match[1]) for key in rows
                           if (match := re.fullmatch(re.escape(prefix) +
                                                    r"infoList\.(\d+)\.name", key))})
        if integer(prefix + "infoList.recorded_keys") != len(item_ids):
            raise ValueError("Quest record count does not match the report")
        groups.append({"index": group_id, "location_id": location,
                       "location": LOCATION_NAMES.get(location, "unknown"),
                       "quest_records": len(item_ids)})
        for item_id in item_ids:
            item = prefix + "infoList.%d." % item_id
            name = rows[item + "name"]
            redacted = name == "<string omitted>"
            if not redacted and not IDENTIFIER.fullmatch(name):
                raise ValueError("Unexpected quest identifier")
            quests.append({"group": group_id, "index": item_id, "location_id": location,
                           "name": None if redacted else name, "name_redacted": redacted,
                           "is_story": optional_bool(item + "isStory"),
                           "is_once": optional_bool(item + "isOnce"),
                           "gameplay_validation": "not_run"})

    pack_names = sorted({match[1] for key in rows
                         if (match := re.fullmatch(r"quests\.questPackList\.([^.]+)\.recorded_keys", key))})
    if integer("quests.questPackList.recorded_keys") != len(pack_names):
        raise ValueError("Pack registry count does not match the report")
    packs = {}
    for name in pack_names:
        if not IDENTIFIER.fullmatch(name):
            raise ValueError("Unexpected pack registry identifier")
        paths = [value for key, value in rows.items()
                 if re.fullmatch(r"quests\.questPackList\." + re.escape(name) + r"\.\d+", key)]
        if any(not re.fullmatch(r"/Assets/tpp/pack/[A-Za-z0-9_./-]+", path) for path in paths):
            raise ValueError("Unexpected asset metadata path")
        packs[name] = sorted(paths)
    named = {item["name"] for item in quests if item["name"] is not None}
    locations = Counter(item["location_id"] for item in quests)
    functions = sorted(key[4:] for key, value in rows.items()
                       if key.startswith("api.") and value == "function")
    return {
        "kind": "runtime_registry_observation_not_gameplay_validation",
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "summary": {"groups": len(groups), "quest_records": len(quests),
                    "named_quest_records": sum(item["name"] is not None for item in quests),
                    "unique_quest_names": len(named),
                    "redacted_quest_names": sum(item["name_redacted"] for item in quests),
                    "pack_registry_entries": len(packs), "gameplay_validated_entries": 0},
        "locations": [{"id": location, "name": LOCATION_NAMES.get(location, "unknown"),
                       "quest_records": count} for location, count in sorted(locations.items())],
        "groups": groups, "quests": quests, "pack_registry": packs,
        "named_quests_without_pack_registry_entry": sorted(named - packs.keys()),
        "pack_entries_without_named_quest_record": sorted(packs.keys() - named),
        "observed_functions": functions,
        "limitations": [
            "This is a snapshot of registered quests, not proof that every Side Op is enumerated.",
            "Registered quests can include special encounters; do not label every record a Side Op.",
            "Absent flags remain unknown rather than being inferred false.",
            "An absent pack entry is not proof of a missing asset or a gameplay bug.",
            "Session-connected state is not a peer count and does not prove a second player.",
            "Function names reveal neither calling conventions nor safe completion/reward behavior."
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = catalog(args.report.read_bytes())
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(result, target, indent=2)
            target.write("\n")
    except (OSError, ValueError) as error:
        print("Inventory catalog: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
