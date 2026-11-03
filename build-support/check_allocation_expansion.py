#!/usr/bin/env python3
"""Offline validation for the profile-preserving prototype; no owner game files."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools/mgsv-pack-report"
FIXTURES = ROOT / "build-cache/controller-fixtures"


def run():
    source = Path(os.environ.get("DYNAMITE_SOURCE_DIR", str(ROOT.parent / "dynamite")))
    cache = subprocess.check_output(["go", "env", "GOMODCACHE"], cwd=MODULE, text=True).strip()
    subprocess.run(["go", "mod", "verify"], cwd=MODULE, check=True, timeout=60)
    command = ["go", "run", "../../build-support/prepare_controller_fixtures.go"]
    subprocess.run(command + [str(source), cache, str(FIXTURES)], cwd=MODULE, check=True, timeout=120)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p",
                    "test_allocation_expansion.py", "-v"], cwd=ROOT, check=True, timeout=60)
    sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
    from test_free_roam_allocation import pack
    from expand_free_roam_allocation import expand_package
    for name, profile in (("Normal", "0000bc3759d825c8"), ("NormalScarf", "0000c94e97c2d50c")):
        fox_body = (FIXTURES / ("synthetic_profile_" + name + ".fox2")).read_bytes()
        member = "/Assets/tpp/level_asset/chara/player/game_object/single_player2_instance.fox2"
        data = pack([("/Assets/test/a.bin", b"SYNTHETIC_A"), (member, fox_body), ("/Assets/test/b.bin", b"SYNTHETIC_B")],
                    ["/Assets/test/external.fpk"])
        target = {"member": member, "member_count": 3, "member_size": len(fox_body),
                  "member_sha256": hashlib.sha256(fox_body).hexdigest(),
                  "package_sha256": hashlib.sha256(data).hexdigest(), "parts_profile_hash": profile}
        output = expand_package(data, target)
        before, after = FIXTURES / (name + "-before.fpkd"), FIXTURES / (name + "-after.fpkd")
        before.write_bytes(data)
        after.write_bytes(output)
        subprocess.run(command + ["--verify-expanded", str(before), str(after)], cwd=MODULE, check=True, timeout=120)


if __name__ == "__main__":
    run()
