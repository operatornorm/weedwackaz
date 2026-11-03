# Development Dynamite source patches

Base: official v0.6.0 commit 7fe74d31128ed8d3741b07181cb99e4adc1f57be.
Keep upstream attribution and [GPLv3 plus Commons Clause license](DYNAMITE-LICENSE).
These are development source patches, not an upstream release or all-content mod.

Changes cover conditional Lua cleanup, native packet-size/received-length checks,
and a link-tested optional CRT diagnostic. No mission eligibility was expanded.

Apply only to a separate source checkout, never to game archives:

    git -C /path/to/dynamite apply --check /path/to/0001-dynamite-lifecycle-and-packet-bounds.patch
    git -C /path/to/dynamite apply /path/to/0001-dynamite-lifecycle-and-packet-bounds.patch

Set DYNAMITE_SOURCE_DIR to that patched checkout for the portable tests. The Windows
DLL cross-build and full Windows/Linux installer packaging passed. Windows game
loading and installation have not run; only Linux's help command was exercised
offline without game files or saves. Standalone DLL installation would omit the
Lua change; do not treat the DLL as the complete patch.

Patch export includes the new WireBounds.h file and was applied to a fresh baseline
copy of all touched files, then byte-compared against the development source.
No game assets, accounts or saves are included.

Apply 0002-dynamite-initial-sync-readiness.patch after 0001. It changes initial
seed/appearance handler tracking, not eligibility or world/session readiness.
Both patches applied in order to a fresh baseline and all seven resulting source
files byte-matched the development checkout. Actual lifecycle tests reject empty-map
readiness and missing Stop invalidation mutations. Current native/installer builds
include both patches; no owner game files have been changed by the agent.

Apply 0003-dynamite-dormant-free-roam-adapter.patch after 0002. It adds a data-only
manifest, a default-inactive adapter and actual Free Roam loader/lifecycle hooks.
Production registers no verification provider or playable startup caller, so this
does not enable expanded co-op. It uses unique staged aliases instead of changing
the original Free Roam package paths. No staged asset writer is supplied.

At the 0003 milestone, all three patches applied in order to fresh baseline files;
all 12 resulting source files and executable mode bits matched that checkout. For
the current source, including 0004, reproduce the full chain check with:

    python3 build-support/export_runtime_observation_patch.py --source /path/to/dynamite --verify-only

The adapter has 22 Lua 5.1 source-callback regressions; the full portable suite has
113 passing checks. A Go packaging test verifies embed/mapping/load declarations.
Read [the integration status](../docs/free-roam-integration.md) before using this
development source. Neither native verification nor real multiplayer is claimed.

Apply 0004-dynamite-runtime-observations.patch after 0003. It adds the passive native
binding and on-demand Lua observer, plus synchronized bookkeeping reads and a
locked initial-handler inspection. No transport, automatic sampler, verification
provider or activation is added. Eight new checks pass, including the actual C++
binding with a real Lua 5.1 VM and two rejected mutations. The full suite now passes
121 portable checks. Both Windows/Linux packages include the rebuilt native DLL;
no installer or real game session has been exercised. The four-patch chain freshly
applies and byte/mode-matches all 19 current source files. Earlier patches stay frozen.

Apply 0005-dynamite-opt-in-status-file.patch after 0004. It adds the explicitly opt-in
local observation transport, normal-update polling and reload/termination fences.
Normal CMake builds set DYNAMITE_QA_STATUS_FILE=OFF; explicit QA builds also need a
fresh fixed-format request before writing bounded atomic status files. The source
includes an unchanged pinned MIT JSON helper with its license. No sockets, invite
handling, gameplay activation or save redirection are introduced.

The current five-patch chain byte/mode-matches 24 source files; verify it with:

    python3 build-support/export_status_bridge_patch.py --verify-only

The full portable suite passes 135 checks. Both default-disabled and explicit-QA
Windows DLLs build, and Windows/Linux QA packages contain exact current Lua modules
and source DLL. These are development artifacts; do not install against live game/
userdata. See docs/NEXT-STEPS.md and docs/status-bridge.md for the deployment gate.

Apply 0006-dynamite-steam-invite-bindings.patch after 0005. It adds pinned flat API
binding, the callback ABI/queue, a strict join-intent protocol and a default-disabled
read-only loaded-module probe. Production registers no new callback and sends no
invitation. No role/config/mission change or broad rich-presence cleanup is wired.
Valve SDK headers/binaries are not included; own declarations derive verified ABI
facts from official pinned source, referenced in docs/steam-invites.md.

Six patches fresh-apply and byte/mode-match 28 source files. Reproduce with:

    python3 build-support/export_steam_invites_patch.py --verify-only

At the 0006 milestone the suite passed 142 portable checks; default/QA Windows DLLs
and Windows/Linux packages built. The separate synthetic Windows fixture subsequently
received an owner-supplied PASS for our cross-DLL binding/callback flow. It used no
real Steam/MGSV and does not validate Steam delivery or MGO routing.

Apply 0007-dynamite-inactive-invite-controller.patch after 0006. It adds in-memory
host/guest selection, deferred warm/cold intent, verified-frame/action-generation
fences and cleanup ownership. Exact action acknowledgments and immutable ownership
identities keep ambiguous failures/reentrancy/late results from reviving an old
context. Its engine adapter and legacy Config/FOX hook migration remain unfinished;
there is no production instance or callback registration. AwaitingPeer is not Joined.
See docs/steam-invites.md for caller cleanup and SDK/module lifetime requirements.

Seven patches fresh-apply and byte/mode-match 30 current source files:

    python3 build-support/export_invite_controller_patch.py --verify-only

The original controller/Sandbox checkpoint passed 163 checks, including 15 controller checks, the
standalone Steam-runtime helper pipeline against fake APIs and five Sandbox-plan/
report tests. The owner-approved real standalone Steam binding/registration result
subsequently passed; actual delivery and borrowed in-game context remain unverified.
The separate offline Sandbox prerequisite helper requests no account/game actions
or software installation. Do not deploy QA game packages until runtime save
isolation and remaining game contracts are verified. No game client or real
invitation has run.

The 4 November 2026 source checkpoint passes 181 portable checks, including the
subsequent preparation/report validators. The seven source patches are unchanged
and still freshly reproduce all 30 modified files. See
[the checkpoint summary](../qa/validation-2026-11-04.txt).
