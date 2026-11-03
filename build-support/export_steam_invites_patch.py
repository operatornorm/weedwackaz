#!/usr/bin/env python3
"""Export verified-interface invite groundwork after frozen source patches0001–0005."""
import export_status_bridge_patch as previous

exporter=previous.exporter
exporter.PREVIOUS=exporter.PREVIOUS+(exporter.OUTPUT,)
exporter.OUTPUT=exporter.ROOT/'patches/0006-dynamite-steam-invite-bindings.patch'
exporter.ADAPTER_FILES=(
    'hook/CMakeLists.txt','hook/src/DynamiteLua.cpp','hook/src/DynamiteLua.h',
    'hook/src/SteamInviteProtocol.h','hook/src/SteamInviteBindings.h','hook/src/SteamInviteProbe.h','hook/src/SteamInviteProbe.cpp',
)
exporter.NEW_BASELINE_FILES.update((
    'hook/src/SteamInviteProtocol.h','hook/src/SteamInviteBindings.h','hook/src/SteamInviteProbe.h','hook/src/SteamInviteProbe.cpp',
))

if __name__=='__main__':exporter.main()
