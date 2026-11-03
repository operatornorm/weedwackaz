# Full-coverage co-op development

Target: every story mission (including prologue and variants), all Side Ops and
Free Roam. Two players first, Windows primary, Proton secondary; four players later.
Both players' separate co-op saves must receive completion and rewards while original
single-player saves remain separate. Host authority needs ordered, deduplicated
completion/reward application rather than copying a whole host profile.

## Source audit

Baseline: [official v0.6.0](https://github.com/unknown321/dynamite/tree/7fe74d31128ed8d3741b07181cb99e4adc1f57be),
regular Steam game 1.0.15.3. No game files or clients are in the cloud.
The [inventory](../qa/coverage-inventory.json) lists prologue plus missions 1-50 and
three source-known Free Roam containers. A runtime registry snapshot has now been
cataloged privately: 160 quest records, 159 named and one redacted. Numbered Side Op
mapping and proof of inventory completeness remain pending.
Old misc notes supply names/IDs only, never current compatibility evidence.

| Observed in source | Work required |
|---|---|
| 36 explicitly eligible IDs, 52 package patches across 35 story IDs | Distinguish eligibility, assets, implementation and tested coverage. |
| Free Roam lacks co-op startup/essentials | Player allocation, quest authority, streaming and transitions. |
| Aliases can overwrite hard-mode IDs with base IDs | Preserve variant identity and original rules. |
| Mission 46 eligible in code, documented disabled, missing pack integration | Resolve policy/assets contradiction; no live crash is claimed. |
| Some objective variables have sync=false; coarse end state does sync | General objective/story authority and join snapshots. |
| End disconnects sessions; checkpoint/next destination are local | Party lifecycle, recovery and travel protocol. |
| Custom sync initializes a small appearance/random-seed set | Do not equate its flag with complete world readiness. |

Sources: [TppMain](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/moddata/standalone/TppMain.lua),
[loaders](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/moddata/standalone/TppMissionList.lua),
[packages](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/moddata/moddata.go),
[mission state](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/moddata/standalone/TppMission.lua),
[wire schema](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/hook/src/DynamiteSyncImpl/DynamiteSyncSchema.fbs).

## Preliminary changes and evidence

[Source patch](../patches/0001-dynamite-lifecycle-and-packet-bounds.patch):

- Fix a shadowed OnTerminate parameter so an online cleanup path calls the module
  predicate. Preserve sequence callback order/guards. Normal completion often clears
  online status earlier; this is not a proven fix for the documented restart hang.
- Align sender/receiver payload capacity at 1024 bytes, validate signed input lengths,
  and give FlatBuffers the actual payload length. Other decoder issues remain.
- Link-check an optional CRT abort-message function; preserve other crash handlers.
- [Patch 0002](../patches/0002-dynamite-initial-sync-readiness.patch) invalidates initial
  seed/appearance tracking on reset/stop, rejects empty and unsolicited completion,
  locks the tracking map and rejects handler completions overlapping a local reset.
  It does not establish peer liveness, full-array coverage or world readiness.

The Windows x64 DLL cross-build passed with MinGW GCC 14.2/CMake 3.31.6 and pinned
dependencies. Its system imports and DirectInput8Create export were inspected.
It has not run in Windows. The standalone DLL does not contain the Lua fix and does
not add mission coverage. Source-derived assets generated successfully. Both Windows
and Linux installers now compile; only the Linux help command has been exercised,
in a read-only offline container without game files or saves.

The cloud container is installed and uses digest-pinned official images, signed APT
packages and verified Git/module pins. The [build script](../build-support/build.sh)
records the build stages. The previous SQLite module download blocker is resolved:
after the owner published the environment, a read-only range check followed the
module proxy redirect to storage.googleapis.com and returned HTTP 206 through the
configured proxy. Complete installer packaging subsequently passed for both targets,
and an offline go mod verify passed after the builds. No installation was performed.

Portable checks: six actual-module Lua lifecycle tests, two production-used C++ bounds
tests, thirteen native-log collector checks, twelve report-extractor checks, seven
catalog checks, three initial-sync lifecycle/mutation checks, nine Python archive
reporter checks, twelve allocation identity/preservation checks, ten controller
structure/transform/packaging checks, nine profile-expansion/support checks and
eight stand-in launcher tests. All91 passed under Lua 5.1.5.
The standalone archive reporter has15 Go checks (synthetic and pinned independent
upstream fixtures) plus a bounds mutation check.
Old scoping/size bug mutations
are caught; real Lua exports round-trip through the extractor with a stubbed native logger.
These are not game, co-op, Windows-runtime or mission completion tests.

## Next gates

1. Map observed registry entries to numbered Side Ops, including redacted/special
   entries. A complete non-truncated runtime metadata report has been received.
2. The corrected stock Free Roam metadata capture passes the development identity
   preflight and all three stock controller structures match. Profile-preserving
   expansion and support splitting pass reference/synthetic/native-reader checks.
   Verify two-player resource/profile compatibility and lifecycle integration before activation.
3. Establish automated tests on both Windows PCs: roles, live peers, world identity,
   visibility, enemies/objectives, extraction, dual-save completion/rewards and unchanged
   original-save hashes. Deliberately broken cases must fail.
4. Implement lifecycle, checkpoint/travel and host quest authority; add content adapters
   against real-client tests, then validate Proton separately.

The patch keeps unsupported content disabled. Every content case remains not_run
until actual passing game evidence exists.
