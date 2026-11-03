#!/usr/bin/env python3
"""Build one deterministic standard-library Python zip application. No downloads."""

from pathlib import Path
import hashlib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build-artifacts/controller-check/mgsv-controller-check.pyz"


def build():
    files = {name: (ROOT / "tools" / name).read_bytes() for name in (
        "mgsv_pack_report.py", "plan_free_roam_allocation.py", "mgsv_fox2.py", "inspect_free_roam_controllers.py")}
    files["allocation_manifest.json"] = (ROOT / "qa/free-roam-allocation-fingerprints.json").read_bytes()
    files["THIRD_PARTY_NOTICES.txt"] = (ROOT / "tools/controller-check-notices.txt").read_bytes()
    files["__main__.py"] = b'''import json,sys,zipfile
from inspect_free_roam_controllers import main
with zipfile.ZipFile(sys.argv[0]) as app:
    manifest=json.loads(app.read("allocation_manifest.json"))
sys.exit(main(manifest=manifest))
'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as app:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            app.writestr(info, data)
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_name("SHA256SUMS").write_text(digest + "  " + OUTPUT.name + "\n")
    print(OUTPUT.name, OUTPUT.stat().st_size, digest)


if __name__ == "__main__":
    build()
