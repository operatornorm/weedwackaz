#!/usr/bin/env python3
"""Export/fresh-apply passive native observations after the frozen adapter patch."""
import export_free_roam_patch as exporter

exporter.PREVIOUS = exporter.PREVIOUS + (exporter.OUTPUT,)
exporter.OUTPUT = exporter.ROOT / "patches/0004-dynamite-runtime-observations.patch"
exporter.ADAPTER_FILES = (
    "hook/src/CoopRuntimeObservation.h", "hook/src/DynamiteCore.h",
    "hook/src/DynamiteLua.cpp", "hook/src/DynamiteLua.h",
    "hook/src/DynamiteSyncImpl/InitialVarSync.h", "hook/src/DynamiteSyncImpl/DynamiteSyncImpl.h",
    "moddata/moddata.go", "moddata/standalone/Tpp.lua",
    "moddata/standalone/WWRuntimeObservation.lua", "moddata/runtime_observation_test.go",
)
exporter.NEW_BASELINE_FILES.update((
    "hook/src/CoopRuntimeObservation.h", "moddata/standalone/WWRuntimeObservation.lua",
    "moddata/runtime_observation_test.go",
))

if __name__ == "__main__":
    exporter.main()
