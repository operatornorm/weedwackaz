#!/usr/bin/env python3
"""Export the test-only local status transport after frozen patches0001–0004."""
import export_runtime_observation_patch as previous

exporter=previous.exporter
exporter.PREVIOUS=exporter.PREVIOUS+(exporter.OUTPUT,)
exporter.OUTPUT=exporter.ROOT/'patches/0005-dynamite-opt-in-status-file.patch'
exporter.ADAPTER_FILES=(
    'hook/CMakeLists.txt','hook/src/CoopStatusFile.h','hook/src/DynamiteLua.cpp','hook/src/DynamiteLua.h',
    'hook/third_party/coopbridge/json.h','hook/third_party/coopbridge/LICENSE','hook/third_party/coopbridge/SOURCE.md',
    'moddata/moddata.go','moddata/standalone/Tpp.lua','moddata/standalone/TppMain.lua',
    'moddata/standalone/WWRuntimeBridge.lua','moddata/runtime_observation_test.go',
)
exporter.NEW_BASELINE_FILES.update((
    'hook/src/CoopStatusFile.h','hook/third_party/coopbridge/json.h','hook/third_party/coopbridge/LICENSE',
    'hook/third_party/coopbridge/SOURCE.md','moddata/standalone/WWRuntimeBridge.lua',
))

if __name__=='__main__':exporter.main()
