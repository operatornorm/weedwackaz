#!/usr/bin/env python3
"""Export and fresh-apply the adapter after patches 0001/0002; source files only."""

import argparse
import difflib
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "7fe74d31128ed8d3741b07181cb99e4adc1f57be"
ADAPTER_FILES = (
    "moddata/moddata.go", "moddata/free_roam_test.go", "moddata/standalone/Tpp.lua",
    "moddata/standalone/TppMain.lua", "moddata/standalone/TppMissionList.lua",
    "moddata/standalone/WWFreeRoam.lua", "moddata/standalone/WWFreeRoamManifest.lua",
)
PREVIOUS = tuple(ROOT / "patches" / name for name in (
    "0001-dynamite-lifecycle-and-packet-bounds.patch",
    "0002-dynamite-initial-sync-readiness.patch",
))
OUTPUT = ROOT / "patches/0003-dynamite-dormant-free-roam-adapter.patch"
NEW_BASELINE_FILES = {
    "hook/src/DynamiteSyncImpl/WireBounds.h", "hook/src/DynamiteSyncImpl/InitialVarSync.h",
    "moddata/free_roam_test.go", "moddata/standalone/WWFreeRoam.lua",
    "moddata/standalone/WWFreeRoamManifest.lua",
}


def apply(directory, patch):
    for arguments in (("--check",), ()):
        subprocess.run(["git", "apply", *arguments, str(patch)], cwd=directory, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT.parent / "dynamite")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    paths = set(ADAPTER_FILES)
    for patch in PREVIOUS:
        paths.update(re.findall(r"^diff --git a/(\S+) b/\S+$", patch.read_text(), re.MULTILINE))
    with tempfile.TemporaryDirectory(prefix="mgsv-adapter-patch-") as temporary:
        directory = Path(temporary)
        for path in sorted(paths):
            baseline = subprocess.run(["git", "show", BASE + ":" + path], cwd=args.source, capture_output=True)
            if baseline.returncode == 0:
                target = directory / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(baseline.stdout)
                entry = subprocess.check_output(["git", "ls-tree", BASE, "--", path], cwd=args.source)
                target.chmod(0o755 if entry.startswith(b"100755 ") else 0o644)
            elif (args.source / path).is_file() and path not in NEW_BASELINE_FILES:
                raise RuntimeError("Unexpected missing baseline source: " + path)
        for patch in PREVIOUS:
            apply(directory, patch)
        if not args.verify_only:
            chunks = []
            for path in ADAPTER_FILES:
                target = directory / path
                before = target.read_bytes().decode("utf-8") if target.exists() else ""
                after = (args.source / path).read_bytes().decode("utf-8")
                if before == after:
                    continue
                chunks.append("diff --git a/" + path + " b/" + path + "\n")
                if not target.exists():
                    chunks.append("new file mode 100644\n")
                for line in difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                                fromfile="a/" + path if target.exists() else "/dev/null",
                                                tofile="b/" + path):
                    chunks.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
            OUTPUT.write_text("".join(chunks))
        apply(directory, OUTPUT)
        for path in paths:
            if (directory / path).read_bytes() != (args.source / path).read_bytes():
                raise RuntimeError("Fresh patch chain differs from source: " + path)
            if ((directory / path).stat().st_mode ^ (args.source / path).stat().st_mode) & 0o111:
                raise RuntimeError("Fresh patch chain differs in executable mode: " + path)
    print("Fresh", len(PREVIOUS) + 1, "patch application and byte comparison passed:", len(paths), "source files")
    print(OUTPUT.name, hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
