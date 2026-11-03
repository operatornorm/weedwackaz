#!/usr/bin/env python3
"""Route Steam's existing Proton command to a separate MGSV copy.

Usage in Steam Launch Options:
python3 /path/launch_mgsv_coop.py --game-dir /path/to/copy -- %command%

This separates the game directory and Proton prefix, not Steam account userdata.
It does not install Dynamite, edit Steam settings, or test gameplay.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def inside(path, parent):
    return os.path.commonpath([str(path), str(parent)]) == str(parent)


def plan_launch(args, inherited):
    game_dir = Path(args.game_dir).expanduser().resolve(strict=True)
    exe = game_dir / "mgsvtpp.exe"
    if not exe.is_file():
        raise ValueError("The co-op directory must contain mgsvtpp.exe")
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        raise ValueError("Steam's command is missing; append -- %command% in Launch Options")
    matches = [i for i, arg in enumerate(command)
               if not arg.startswith("-") and
               arg.replace("\\", "/").rsplit("/", 1)[-1].lower() == "mgsvtpp.exe"]
    if len(matches) != 1 or matches[0] == 0:
        raise ValueError("Expected exactly one game argument in Steam's Proton command")
    if args.expected_sha256:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", args.expected_sha256):
            raise ValueError("Expected SHA-256 must contain 64 hexadecimal characters")
        digest = hashlib.sha256()
        with exe.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != args.expected_sha256.lower():
            raise ValueError("Copied executable SHA-256 does not match; nothing launched")
    if not args.dry_run and not (game_dir / "dinput8.dll").is_file():
        raise ValueError("Dynamite's dinput8.dll is missing from the co-op copy")

    prefix = Path(args.prefix).expanduser().resolve()
    if inside(prefix, game_dir):
        raise ValueError("Keep the Proton prefix outside the shared game directory")
    original_prefix = inherited.get("STEAM_COMPAT_DATA_PATH")
    if original_prefix and prefix == Path(original_prefix).expanduser().resolve():
        raise ValueError("The co-op prefix must differ from Steam's original prefix")

    overrides = inherited.get("WINEDLLOVERRIDES", "")
    for entry in overrides.split(";"):
        names, separator, value = entry.partition("=")
        if separator and any(name.strip().lower() in ("dinput8", "dinput8.dll")
                             for name in names.split(",")):
            if value.replace(" ", "").lower() != "n,b":
                raise ValueError("Remove the conflicting dinput8 override from Launch Options")
    command[matches[0]] = str(exe)
    env = dict(inherited)
    env["STEAM_COMPAT_DATA_PATH"] = str(prefix)
    env["STEAM_COMPAT_INSTALL_PATH"] = str(game_dir)
    mounts = [p for p in env.get("STEAM_COMPAT_MOUNTS", "").split(":") if p]
    if str(game_dir) not in mounts:
        mounts.append(str(game_dir))
    env["STEAM_COMPAT_MOUNTS"] = ":".join(mounts)
    env["WINEDLLOVERRIDES"] = ";".join(
        value for value in (overrides, "dinput8.dll=n,b") if value)
    env["PROTON_LOG"] = "1"
    env["PROTON_LOG_DIR"] = str(prefix.parent / "logs")
    summary = {
        "game_executable": str(exe),
        "working_directory": str(game_dir),
        "proton_prefix": str(prefix),
        "proton_log_directory": env["PROTON_LOG_DIR"],
        "note": "Launch routing only; Steam account userdata is not isolated.",
    }
    return command, env, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", required=True)
    parser.add_argument("--prefix", default=str(
        Path.home() / ".local/share/mgsv-coop/compatdata"))
    parser.add_argument("--expected-sha256")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print routing without launching or creating files")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        command, env, summary = plan_launch(args, os.environ)
        if args.dry_run:
            print(json.dumps(dict(summary, command=command), indent=2))
            return 0
        Path(env["STEAM_COMPAT_DATA_PATH"]).mkdir(parents=True, exist_ok=True)
        Path(env["PROTON_LOG_DIR"]).mkdir(parents=True, exist_ok=True)
        log = Path(env["PROTON_LOG_DIR"]).parent / "last-launch.json"
        log.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        os.chdir(summary["working_directory"])
        os.execvpe(command[0], command, env)
    except (OSError, ValueError) as exc:
        print("MGSV co-op launcher: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
