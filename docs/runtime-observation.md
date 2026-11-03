# Passive runtime observations

Patch 0004 adds a read-only native binding and an on-demand Lua reader. This is the
first measurement layer for the verification bridge. It supplies no production
readiness receipt and does not enable Free Roam or Side Ops. No new owner capture
or installation is requested for this development slice.

## Implemented interfaces

`Dynamite.ReadRuntimeObservation()` returns one fixed-size scalar table using the
Lua state supplied by its caller. It uses only table/scalar functions already
mapped in the pinned 1.0.15.3 native source. It never calls Lua using a cached state.

| Fields | Meaning |
|---|---|
| configured_role | Configured host/client role, not network authority. |
| session_created_bookkeeping, host_session_created_bookkeeping | Results remembered from creation attempts. |
| session_connected_bookkeeping | Established-callback latch; it can remain true after disconnect. |
| member_query_status, optional engine_member_count | Explicit availability plus an actual bounded native query result. Missing session/API never becomes a synthetic count 1. |
| sample_id | Decimal-string diagnostic counter local to this DLL instance. It saturates instead of wrapping. |
| initial_vars_generation, initial_vars_required, initial_vars_applied | One locked inspection of the existing required-handler tracker. Generation is a local counter, not a wire epoch. |
| initial_vars_handlers_complete | All tracked handlers applied; complete array/session/world synchronization remains unverified. |

Missing native context returns native_available=false and configured_role=unknown.
Unknown member count is omitted. The existing native session/+0x20 query layout is
reused; counts outside 0–16 are rejected. This layout applies to the pinned regular
executable, not arbitrary versions. Three existing bookkeeping fields are atomic
at their actual readers/writers. That prevents races on those fields; it does not
make the successive engine readings a coherent snapshot.

`WWRuntimeObservation.Snapshot()` combines a filtered native observation with
protected, source-backed Lua getters for current mission/location, sequence name/
index, preparation, nonplayable state, world center and local position. It queries
only player slots 0/1 and only when the engine NULL_ID sentinel is available.
Player-slot presence is distinct from realization and ownership. World vectors
use existing GetX/GetY/GetZ accessors with finite bounds. Missing, malformed or
throwing APIs remain unknown; error strings and arbitrary native fields are not
copied into the result.

Both layers always return observation_only=true and can_authorize=false. Peer
liveness, player realization, world/center agreement, full initial synchronization,
wire epochs, playable Free Roam and save isolation are not verified by this API.
Even a two-member engine session with both slots present cannot authorize startup.
Diagnostic sample IDs cannot establish a peer heartbeat or identify a process
restart. They must not be compared across clients or DLL instances.

## Execution boundary

The Lua module has no automatic dispatch/update functions, sampler, transport or
writer. Nothing registers it as a Free Roam proof provider or calls TryStart.
Snapshots run only when a future harness explicitly calls from an owning Lua
context. The source does not prove that context's OS-thread identity or every
getter's engine lifetime safety. Lua pcall cannot catch native memory faults.
Real-game validation of the API and call timing is still required.

Coop Anything's MCP server supplies repository knowledge tools. It does not itself
create an MGSV bridge or grant access to another PC. A future test transport can
reuse its bounded main-thread bridge protocol with a custom read-only status
method. Transport startup/shutdown must occur outside DllMain. Arbitrary eval,
save/load and file-writing state methods are unnecessary for this slice.

## Executed checks

Eight new checks exercise the actual readers: the extracted production C++ binding
runs against a real Lua 5.1 VM with native engine stubs and a caller-stack sentinel;
the actual Lua module runs with known, missing and throwing APIs. They cover native
query availability and bounds, exact/concurrent/exhausted counters, locked tracker
inspection, stale bookkeeping, vector bounds, fixed-slot queries and output filtering.
Two mutations deliberately fabricate solo membership or verified peer liveness;
the tests reject both. They are game-free software checks, not native-game QA.

Windows DLL cross-build and Windows/Linux packages pass offline. Two Go tests
verify embedded module mappings/declarations. Actual installer binaries contain
the six current relevant Lua modules and the rebuilt source DLL exactly once.
Linux help runs; PE/ELF metadata and DLL imports/export inspect successfully.
No installation or real-game client ran. Four patches fresh-apply and all 19 source
files and executable modes match the development source.

Reproduce the current patch-chain check:

    python3 build-support/export_runtime_observation_patch.py --source /path/to/dynamite --verify-only

Cloud build logs are under build-logs/runtime-observation-*.log. Current hashes and
test counts are recorded in qa/build-status.json. Development binaries remain in
ignored build-artifacts/experimental-runtime-observation, with activation disabled.
