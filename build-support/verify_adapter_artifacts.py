#!/usr/bin/env python3
"""Require both packaged binaries to contain the exact current embedded modules."""

import argparse
import hashlib
from pathlib import Path

MODULES = ("Tpp.lua", "TppMain.lua", "TppMissionList.lua", "WWFreeRoam.lua", "WWFreeRoamManifest.lua")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--runtime-observation", action="store_true")
    parser.add_argument("--status-bridge", action="store_true")
    args = parser.parse_args()
    dll = (args.source / "hook/cmake-build-release-docker-mingw15/dinput8.dll").read_bytes()
    if not args.runtime_observation and hashlib.sha256(dll).hexdigest() != "ba9c77e6dfa818b01845e41f8cc96015c4dcf30877716a778ab2d73c1491d35f":
        raise RuntimeError("Core DLL differs from the separately validated build")
    if (args.artifacts / "dinput8.dll").read_bytes() != dll:
        raise RuntimeError("Packaged DLL differs from this build's embedded source DLL")
    modules = MODULES + (("WWRuntimeObservation.lua",) if args.runtime_observation else ())
    if args.status_bridge: modules += ("WWRuntimeBridge.lua",)
    for name in ("dynamite-windows-amd64.exe", "dynamite-linux-amd64"):
        binary = (args.artifacts / name).read_bytes()
        for module in modules:
            source = (args.source / "moddata/standalone" / module).read_bytes()
            if binary.count(source) != 1:
                raise RuntimeError(name + " does not contain exactly one current " + module)
        if binary.count(dll) != 1:
            raise RuntimeError(name + " does not contain exactly one validated core DLL")
        print(name, "exact current modules and source DLL embedded")


if __name__ == "__main__":
    main()
