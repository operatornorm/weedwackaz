#!/usr/bin/env python3
"""Inventory source declarations; never treat eligibility as gameplay validation."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess


def inventory(source):
    main = (source / "moddata/standalone/TppMain.lua").read_text(encoding="utf-8")
    packages = (source / "moddata/standalone/TppMissionList.lua").read_text(encoding="utf-8")
    manifest = (source / "moddata/moddata.go").read_text(encoding="utf-8")
    names = (source / "misc/missionlist.md").read_text(encoding="utf-8")
    match = re.search(r"function e\.IsCoop\(missionCode\).*?local coops\s*=\s*\{(.*?)\}",
                      main, re.S)
    if not match:
        raise ValueError("Unknown eligibility source format; review the extractor")
    literal = "\n".join(line.split("--", 1)[0] for line in match[1].splitlines())
    enabled = {int(value) for value in re.findall(r"\b\d+\b", literal)}
    # The pinned source has a whole-line debug block; embed globs also contain /*.
    manifest = re.sub(r"(?ms)^\s*/\*.*?^\s*\*/\s*$", "\n", manifest)
    if re.search(r"(?m)^\s*/\*", manifest):
        raise ValueError("Go block comments require reviewing the manifest extractor")
    package_paths = re.findall(r'^\s*NameInQar:\s*"([^"]+)"', manifest, re.M)
    direct = Counter()
    for path in package_paths:
        match = re.fullmatch(r"/Assets/tpp/pack/mission2/story/s(\d+)/[^/]+\.fpkd", path)
        if match:
            direct[int(match[1])] += 1
    aliases = {int(a): int(b) for a, b in
               re.findall(r"^s\[(\d+)\]\s*=\s*s\[(\d+)\]", packages, re.M)}
    overwrites = {int(code) for code in re.findall(r"vars\.missionCode\s*=\s*(\d+)", packages)}
    story = []
    for line in names.splitlines():
        match = re.match(r"^\s*[+-]?(\d+)\s*:\s*(?:(\d+)\s*-\s*)?(.+)$", line)
        if not match:
            continue
        code = int(match[1])
        if not 10000 <= code < 12000:
            continue
        number = int(match[2]) if match[2] else 0
        if number == 0 and code != 10010:
            raise ValueError("Unrecognized unnumbered story entry")
        base = aliases.get(code)
        story.append({
            "mission_number": number,
            "game_mission_code": code,
            "name": match[3].split(" - ", 1)[0].strip(),
            "requested": True,
            "upstream_predicate_enabled": code in enabled,
            "direct_story_package_patches": direct[code],
            "loader_alias_of": base,
            "alias_base_writes_base_mission_id": base in overwrites if base else False,
            "gameplay_validation": "not_run",
        })
    if len(story) != 51 or {row["mission_number"] for row in story} != set(range(51)):
        raise ValueError("Story inventory is incomplete or ambiguous; expected prologue and missions 1-50")
    free_roam = [{"game_mission_code": code, "location": location,
                  "requested": True, "upstream_predicate_enabled": code in enabled,
                  "gameplay_validation": "not_run"}
                 for code, location in ((30010, "Afghanistan"),
                                        (30020, "Africa"), (30050, "Mother Base"))]
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    return {
        "kind": "source_inventory_only",
        "source_repository": "https://github.com/unknown321/dynamite",
        "source_commit": commit,
        "target": {"players": 2, "primary_platform": "Windows", "secondary_platform": "Linux/Proton",
                   "story": "all including prologue and variants", "side_ops": "all", "free_roam": "all"},
        "limitations": [
            "Eligibility is not proof of gameplay, correct difficulty, assets or synchronization.",
            "The outdated misc list supplies names/IDs only; its old playability annotations are ignored.",
            "Source declarations do not enumerate all Side Ops or prove completeness of Free Roam locations.",
            "No entry is promoted to tested by this inventory tool.",
        ],
        "summary": {"story_entries": len(story),
                    "explicitly_eligible_story_ids": sum(row["upstream_predicate_enabled"] for row in story),
                    "direct_story_package_patches": sum(direct.values()),
                    "story_ids_with_direct_package_patches": len(direct),
                    "source_known_free_roam_containers": len(free_roam),
                    "gameplay_validated_entries": 0},
        "story": sorted(story, key=lambda row: row["mission_number"]),
        "free_roam": free_roam,
        "side_ops": {"requested": "all", "individual_quest_inventory": "pending",
                     "gameplay_validation": "not_run",
                     "next_input": "Version-matched quest metadata and runtime observations from isolated game copies"},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print("Source inventory generated. Game-level coverage remains unverified.")


if __name__ == "__main__":
    main()
