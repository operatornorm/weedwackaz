#!/usr/bin/env python3
"""Run the pack reporter's synthetic tests and prove its member bounds guard fails closed."""

from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / "tools/mgsv-pack-report"


def run():
    result = subprocess.run(["go", "test", "-count=1", "-v", "./..."], cwd=SOURCE, timeout=180)
    if result.returncode:
        raise SystemExit(result.returncode)
    with tempfile.TemporaryDirectory(prefix="ww-pack-mutant-") as directory:
        target = Path(directory)
        for name in ("go.mod", "go.sum", "main.go", "metadata.go", "metadata_test.go"):
            shutil.copyfile(SOURCE / name, target / name)
        file = target / "metadata.go"
        original = file.read_text()
        guard = "uint64(offset) < tableEnd || !span(uint64(offset), uint64(size), uint64(len(data)))"
        if original.count(guard) != 1:
            raise SystemExit("Member bounds guard changed; review the mutation test")
        file.write_text(original.replace(guard, guard.replace("|| !span", "|| false && !span")))
        mutant = subprocess.run(["go", "test", "-count=1", "-run", "TestFPKBounds/member_span", "-v"],
                                cwd=target, capture_output=True, text=True, timeout=180)
        output = mutant.stdout + mutant.stderr
        if mutant.returncode == 0 or "--- FAIL: TestFPKBounds/member_span" not in output:
            raise SystemExit("Bounds mutation was not caught by the intended test")
    print("ALL OK: synthetic pack metadata checks and member-bounds mutation")


if __name__ == "__main__":
    run()
