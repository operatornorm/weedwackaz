#!/usr/bin/env python3
"""Export inactive invite control after frozen source patches 0001–0006."""
import export_steam_invites_patch as previous

exporter = previous.exporter
exporter.PREVIOUS = exporter.PREVIOUS + (exporter.OUTPUT,)
exporter.OUTPUT = exporter.ROOT / 'patches/0007-dynamite-inactive-invite-controller.patch'
exporter.ADAPTER_FILES = (
    'hook/CMakeLists.txt', 'hook/src/SteamInviteController.h', 'hook/src/SteamInviteController.cpp',
)
exporter.NEW_BASELINE_FILES.update((
    'hook/src/SteamInviteController.h', 'hook/src/SteamInviteController.cpp',
))

if __name__ == '__main__':
    exporter.main()
