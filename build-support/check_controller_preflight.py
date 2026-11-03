#!/usr/bin/env python3
"""Offline controller parser, transform and artifact checks in the approved build image."""

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
    subprocess.run(["go", "run", "../../build-support/prepare_controller_fixtures.go", str(source), cache,
                    str(FIXTURES)], cwd=MODULE, check=True, timeout=120)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p",
                    "test_controller_preflight.py", "-v"], cwd=ROOT, check=True, timeout=60)
    sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
    from test_free_roam_allocation import pack
    from inspect_free_roam_controllers import transform_verified_package
    body = (FIXTURES / "synthetic_single.fox2").read_bytes()
    member = "/Assets/tpp/level_asset/chara/player/game_object/single_player2_instance.fox2"
    data = pack([("/Assets/test/a.bin", b"SYNTHETIC_A"), (member, body), ("/Assets/test/b.bin", b"SYNTHETIC_B")],
                ["/Assets/test/external.fpk"])
    target = {"package_sha256": hashlib.sha256(data).hexdigest(), "member": member, "member_count": 3,
              "member_sha256": hashlib.sha256(body).hexdigest(), "member_size": len(body)}
    output = transform_verified_package(data, target)
    before, after = FIXTURES / "before.fpkd", FIXTURES / "after.fpkd"
    before.write_bytes(data)
    after.write_bytes(output)
    subprocess.run(["go", "run", "../../build-support/prepare_controller_fixtures.go", "--verify-transform",
                    str(before), str(after)], cwd=MODULE, check=True, timeout=120)


if __name__ == "__main__":
    run()
