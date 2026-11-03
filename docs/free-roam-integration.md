# First Free Roam milestone

Target: a verified host plus one live guest in the same Free Roam world, with both
players allocated and visible. Side Op authority and both-save completion follow.
This does not narrow the requested final scope: all story missions, all Side Ops
and Free Roam remain the goal, Windows primary and Proton secondary.

The archive and targeted controller captures now confirm all three initial targets:
normal Afghanistan, its recovery variant and Africa. Each has one controller, one
parts slot and the expected three-entity graph; executable/package/member identities
match. Afghanistan's parts hash matches PLTypeNormalScarf; Africa's matches
PLTypeNormal. This is serialized structure, not realized player count or working
co-op. No further collector run is requested at this stage.

## Verified gaps

- Upstream TppMain.IsCoop omits Free Roam and its loaders omit co-op support.
  The experimental adapter below now wires these paths conditionally. Without its
  missing native verifier and playable hook, Free Roam still takes the original path.
- Existing story patches remove a known single-player FOX2 controller. Free Roam
  package/member identity and stock structure are now confirmed. Two-player resource
  compatibility and shared dependencies still need verification before activation.
- Story sequences separately accept sessions, start targeting and set a world
  center. Free Roam lifecycle timing and the center policy need implementation.
- Solo Free Roam can have an engine session. Session-connected/configured-host
  booleans cannot count a live second player.

## Source correction prepared

[Patch 0002](../patches/0002-dynamite-initial-sync-readiness.patch), applied after 0001,
corrects initial seed/appearance tracking. Fresh, stopped and reset states cannot
report synchronization; only explicitly required svars handlers can complete it.
Map access is locked, and generation tokens reject handlers overlapping a local reset.
This is not peer liveness, a network epoch, full-array validation or world readiness.
The custom request loop still has no live caller; no bootstrap activation is claimed.

Three checks compile the actual lifecycle method bodies with engine stubs and the
production-used tracker. They reject mutations restoring empty-map readiness or
omitting Stop invalidation. The production DLL and Windows/Linux installer builds
passed; Linux help and Windows imports/export were checked offline. No game run
or expanded-content validation has occurred.

## Allocation identity preflight

The [fingerprint manifest](../qa/free-roam-allocation-fingerprints.json) pins three
FPKDs and their loader FPKs: normal Afghanistan, recover-Volgin Afghanistan, and
Africa. The [development planner](../tools/plan_free_roam_allocation.py) accepts the
corrected metadata report and emits a plan with `can_apply=false`. It does not call
the installer, read game files, remove members or enable missions.

For development use, with private capture/output paths:

    python3 tools/plan_free_roam_allocation.py \
      --report "<private v2 capture.json>" \
      --output "<ignored private directory>/allocation-plan.json"

It rejects incomplete/error-marked reports, contradictory probe counts, aliases,
duplicate/override packages, wrong source archives, altered fingerprints, duplicate
members, alternate allocators and existing replacement-controller members. Both
Afghanistan branches must be present. Mother Base/hangar/zoo/ward remain outside
this first plan; differing zoo copies cannot be treated as equivalent.

The current [pure expansion prototype](../tools/expand_free_roam_allocation.py)
preserves the stock controller, its map-specific profile and entity graph. It
changes five properties using the existing two-player model's allocation values:

| Property | Stock | Prototype |
|---|---|---|
| partsBlockCount | 1 | 2 |
| instanceBlockSize | 563200 | 1126400 |
| instancePackagePath | single_player_game_obj.fpk | two_players_game_obj.fpk |
| partsTypeNames | One original profile | Two copies of that profile |
| partsTypeInitial | One original profile | Two copies of that profile |

The other eight properties and DataSet/TexturePackLoadConditioner stay unchanged.
Two hashes fit each existing48-byte array record; both builder and verifier require
zero original padding before using the second slot. Existing literals remain intact;
the new instance path is added or reused with a verified hash. The result is reparsed
and checked against a byte/property allowlist.

FPKD replacement appends the expanded body at an aligned offset and changes only
the file-size field and that member's offset/size fields. The rest of the original
package prefix, unrelated members/references and opaque metadata remain unchanged.
Old controller bytes remain unreferenced. A source fingerprint is rechecked before
transformation; metadata alone cannot authorize a stale package.

The proposed shared pack is coop_free_roam_support, containing exactly the three
unchanged parts/motion support members from the pinned mod essentials. It excludes
two_player2_instances because the mission already supplies its expanded controller.
Current story essentials stay untouched. No installer/application path is exposed.

All 113 portable checks pass, including 9 profile/delta/append/support/report checks
and 22 source-wired adapter checks described below.
The pinned native FPK and FOX2 readers independently accept both Normal and
NormalScarf synthetic expansions and verify the five-property delta and preservation.
The metadata captures pass identity and structure cross-checks. Owner asset bodies
have not been transformed in the cloud, and no game clients ran.

## Dormant loader and lifecycle adapter

[Patch 0003](../patches/0003-dynamite-dormant-free-roam-adapter.patch) applies after
0001 and 0002. It adds the actual Lua loader/lifecycle integration, while keeping
production activation disabled. No bootstrap provider is registered and no playable
sequence calls TryStart. This is a development milestone, not a playable extension.

- Each of the three verified branches has a distinct staged FPK/FPKD alias under
  /Assets/tpp/pack/coop/free/. The original package path stays selected by default.
  Expanded assets must never overwrite an original path used when opt-in is off.
- Pending package selection and the active mission have separate generations.
  Allocation freezes the selected receipt before the first co-op decision and
  rechecks identity, profile, support, companion routing and native host/client role.
  Support is queued once per package list. Ambiguous/failed loads retain a failure
  latch through unrelated mission teardown and abort allocation.
- Initialization, preparation and game-start callbacks record ordered milestones.
  Common game-start can still be in a demo and never opens a session itself.
  Reload invalidates readiness before sequence callbacks while retaining the
  allocated load's cleanup obligation.
- Owned teardown attempts all five native cleanup operations even if one throws
  or returns false. It retains the obligation for retry and invokes the sequence
  finalizer once. Successful old-mission teardown preserves the next selection.
- A future trusted provider must supply fresh, generation/nonce/epoch-bound
  receipts. Package checks also require dependency/profile compatibility, a
  verified lifecycle contract, save isolation and protocol epoch handling. Client
  connection must already exist before package selection and allocation.
- A future playable hook can request startup only after fresh runtime proof of
  the expected session, sequence, role, realized local player and center plan.
  Host acceptance can precede guest arrival; targeting requires two realized
  players, a live peer in the same world, agreed center and initial sync readiness.
  Lost readiness or reentrant invalidation requests rollback and blocks restart.

The Lua receipt interface assumes a trusted native bootstrap; copying test flags
does not implement any of these checks. It is not authentication against arbitrary
Lua code. Successful startup returns only that native calls were issued, not that
the engine acknowledged them or that gameplay synchronized.

The data-only manifest is generated by
[generate_free_roam_manifest.py](../build-support/generate_free_roam_manifest.py)
from pinned source/profile inputs and the separately split support pack. The
planner and manifest share the same staged-path derivation. No staged game-pack
writer or installation path has been added.

Twenty-two tests execute the actual adapter and relevant engine callbacks in Lua
5.1.5 with explicit provider/engine fixtures. They cover default trace parity with
pinned upstream across all three branches, callback ordering, stale reports,
preconnection, player realization, reload, reentrancy, cross-generation failures,
teardown retries and preservation of false/nil callback errors. All 113 portable
checks pass. These are software regressions, not game or multiplayer tests.

## Remaining dependency gate

Preserving the scarf hash does not prove the two-player object supports it. The
official two-player model uses Normal in both slots. Verify profile definitions,
two_players_game_obj.fpk and its companions, online motion and location-motion
packs before activation. The installer copies mtbs_mission_fob.fpk as essentials;
it does not explicitly construct/extract the two-player object pack. Resource
availability cannot be inferred solely from controller references.

Lifecycle research also leaves a concrete runtime gap: the common mission-start
callback can still be in a demo; the pinned checkout has no Free Roam playable
sequence contract. Configuration loaded during script_loader.Update is too late
for package selection. Client connection belongs before mission load due to the
existing allocation lifetime constraint. The dormant hooks enforce this ordering;
no guessed sequence/world center or late enable binding has been added.

## Integration gates

The [passive native observation layer](runtime-observation.md) is now implemented
and tested with engine stubs. It reports known/unknown measurements and cannot
authorize activation. The full portable suite now has 121 passing checks; native
verification and actual game testing remain separate gates.

1. Identity and stock structure are confirmed; profile-preserving expansion and
   support splitting are tested prototypes. Verify resource/profile compatibility
   and staged application with immediate live-byte/preservation guards.
2. Implement the trusted native package/runtime verification producer and a verified
   playable Free Roam sequence hook. The conditional package/lifecycle adapter is
   now in source, with production providers absent. Keep it disabled until the
   dependency, save-isolation and wire-epoch contracts are implemented and verified.
3. Build an in-game main-thread bridge/bot and two-PC scorer. Require fresh samples
   from both Windows clients, expected map, two members, peer progress and correct
   player visibility; deliberately broken cases must fail.
4. Add host-authoritative quest events and idempotent per-profile completion/rewards.
   Observe natural callbacks or verified primitives. Do not guess ClearWithSave's
   arguments from its name; its known caller supplies a result code, not a quest ID.

Original installs/saves remain outside test slots. No Windows remote access, local
installation or account access is implied by availability of the two PCs.
