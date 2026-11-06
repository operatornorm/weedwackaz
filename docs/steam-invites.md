# Steam invitations as the normal join flow

Intended normal behavior: the host invites friends through regular Steam
invitations. A guest accepts and joins automatically. SteamID entry is acceptable
as an interim/fallback method. Cover an already-running guest and a guest whose
game must first launch. Use MGSV's App 287700 and the correct compatible mod copy.

Both methods must work without required router port forwarding. Treat invitation
delivery and the actual game transport separately: verify the existing Steam
peer/relay path and installed interface support, and implement an adapter if needed.
Do not infer NAT traversal or relay success from an accepted invitation. Validate
two PCs on different internet connections, including restrictive NAT and relay
fallback, without depending on manual/automatic router port-mapping configuration.
These transport properties have not yet been verified in the mod.

## Source-backed gaps

The baseline injects cfg.HostSteamID into FOX's connection target. It rejects
client startup with host ID 0 before installing hooks; configured hosts cannot
become guests through CreateClientSession. Invite acceptance therefore needs an
in-memory runtime role/target and deferred validation, not a config-file rewrite.
Existing connection/mission selection is manual. The local Fuse sidecar lives in
the Go process, so cold acceptance needs coordinated launch handling.

The pinned upstream baseline has no SteamFriends invitation bindings. Patch 0006
now contains source-backed ABI declarations and a direct-invitation protocol.
Metadata/source checks and our synthetic Windows test do not establish callable
interfaces inside MGSV. The separate real standalone check below now verifies
binding and callback registration in its own process.

MGSV already has InvitationManager handling that can route accepted invitations
to Mission.SwitchApplication("mgo"). The new co-op invitation path must be
distinguished from it, and must not consume or misroute legitimate MGO invitations.
Invite admission/session identity must expire when hosting ends; accepting an
old invitation must not silently connect to a replacement world/session.

Source references: pinned Dynamite Config.cpp:91, DynamiteHook.cpp:130,
DynamiteLua.cpp:78, cli/cli.go:135, and init_sequence.lua:2700/2851 at official
commit 7fe74d31128ed8d3741b07181cb99e4adc1f57be. No invitation behavior has been tested.

## Capability report accepted

The supplied report matches the pinned executable and 211368-byte AMD64 Steam DLL,
SHA256 08bd0152356e5619ee56a6714ac951b6800dbb21821693a4efaf85278442c60a.
All 12 flat exports required by the implementation are present. The DLL advertises
Friends015/User018/Utils007. The executable also contains older Client015/User017
strings; those are not interchangeable vtable contracts. The adapter obtains fresh
interfaces through the DLL's own exported flat factory functions.

The ABI reference is ValveSoftware/Proton
[e91ca2be0df2cef4c230cbbc0b86604d73a0bbf6](https://github.com/ValveSoftware/Proton/tree/e91ca2be0df2cef4c230cbbc0b86604d73a0bbf6/lsteamclient/steamworks_sdk_135):
steam_api_flat.h signatures; steam_api.h's three-method callback base without a
virtual destructor; callback 337's 264-byte AMD64 payload (SteamID plus 256 chars).
The source contains own minimal declarations of these ABI facts, not redistributed
Valve SDK files. Metadata pins and required names are in qa/steam-invite-bindings.json.

## Implemented groundwork

Patch 0006 adds the actual typed resolver/context binder, callback queue, bounded
invitation protocol and channel. It borrows an initialized Steam context, validates
the actual App 287700 and local identity, and never creates a user/pipe or adds an
Init/Shutdown/RunCallbacks loop. Callback entrypoints only copy bounded data; all
SDK actions/draining run on the bound owner thread. Unregistration suspends actions
first, retains failed cleanup for retry, and requires externally verified callback/
module quiescence before storage or code can be destroyed.

Payloads bind the executable, initial target, host, session, epoch and expiration.
They are data only, including cold-launch arguments. Exact duplicate callbacks are
ignored; explicit renewals can retry. Successful parsing/Steam sending is not peer
authentication or game readiness. Storage generations remain unique across channel
restarts while the storage remains alive. The fixed callback pointer uses the SDK's
size contract; no arbitrary short-pointer safety is claimed.

The native on-demand interface probe is compile-time OFF by default. When explicitly
compiled on, it uses a temporary reference to the already-loaded original Steam DLL,
checks its on-disk SHA256/size with Windows BCrypt, and reports interface binding
status only. It registers no callbacks, sends no invites, writes no rich presence
or configuration and exports no account IDs, addresses or paths.

Production creates no active invite channel or controller. Send gates require native save/resource/
peer-protocol/MGO contracts that are currently unverified. No source raises those
proofs. Host friend selection, FOX role/target/mission integration and cold
sidecar/executable routing remain unfinished. Registering our
listener does not suppress ordinary listeners or prove that MGO will ignore a co-op
invitation. No real Steam invitation or game client has been exercised.

## Synthetic Windows result accepted

The standalone synthetic fixture loads only our fixed ww-invite-fake.dll, resolves
the production flat function table and passes callback data between our two test
modules. It performs no Steam/game/account/save or network operations and needs no
separate Windows login. It writes only an exclusive result JSON beside itself.
It tests Windows loader/binding/callback mechanics, not the real Valve runtime.

The supplied schema-1 report is PASS with reason
synthetic_cross_dll_binding_and_callback. It explicitly reports real_steam_used,
game_launched and co_op_verified as false. The report was preserved privately and
its hash recorded in qa/build-status.json. No rerun is requested.

## Inactive session controller

Patch 0007 adds the main-thread controller that consumes the actual Channel warm
intent and the same validated cold format. It keeps pending selection separate
from the active role/target and cleanup-owned context, without rewriting Config.
It waits for safe loading/sidecar/native contracts, issues preparation/connection
once, and requires a fresh engine generation after preparation. Host expiry can
be explicitly renewed; accepting another host retires the old owned context first.

The engine boundary returns a typed action. Its future adapter must perform that
action once, key owned resources by immutable (run, ownership), and acknowledge the
exact action after settling it. Failure, cancellation, proof/context/world loss,
clock rollback and late acknowledgments retain possible ownership until an observed
release succeeds. Failed release requires explicit retry. Unrelated MGO/FOB sessions
block new work and are never eligible for the controller's cleanup. SDK reentrancy
and foreign-thread operations are rejected. Temporary nonplayable/unknown targets
block sends; a known wrong world, lost sidecar or foreign session revokes the owned
context even when first observed by Send.

AwaitingPeer means only that a connection request completed at the engine boundary;
it does not mean Joined. Real peer authentication/liveness and synchronized world
state still require the unfinished transport protocol. No production engine adapter,
controller instance, Config/FOX hook role migration or proof provider is supplied.
Do not use passive snapshots as WorldFrame contracts. Before destroying controller,
callback or module storage, the caller must finish owned cleanup, Stop successfully
and prove SDK callback/module quiescence. The controller destructor does none of it.

## Real Steam context result accepted

The owner approved and ran ww-steam-runtime-check.zip on Windows. Its schema-1
report is PASS/interfaces_and_registration_verified: initialization, interface
binding, callback registration/unregistration and own shutdown are true. Game
launch, real callback delivery and co_op_verified are false; invitations_sent is0.
The private raw report's SHA256 is
5072d5b65b03072ff65af442b126c561e314c3ba5430f06de1b166af1a181dd0.

The helper initializes its own
standalone context for App 287700, binds exact interfaces, registers/unregisters the
callback and shuts down its own context. It never launches MGSV or pumps callbacks,
sends no invitations, does not enumerate friends and calls no save APIs. Steam may
briefly show MGSV activity and perform normal client bookkeeping. This helper's
Init/Shutdown must never be copied into an injected game's lifetime handling.

It uses the existing co-op copy's pinned DLL through a file picker, verifies it before
LoadLibrary and retains the locked file/module/callback until process exit. It contains
no Valve DLL/SDK headers and changes no Steam or Cloud settings. It writes only its
exclusive fixed-field ww-steam-runtime-result.json beside the helper, without account
IDs/names or paths. This accepts standalone binding/registration only, not borrowed
in-game context, actual delivery, MGO routing, save isolation or gameplay. No rerun
or further Steam-account action is requested now.

## Read-only metadata collector retained for development

The new mgsv-steam-capabilities.pyz reads only the pinned executable hash and the
adjacent steam_api64.dll. It parses PE metadata without loading either binary,
starting Steam/game processes or reading saves/accounts. It reports DLL hash/size,
Steam export names and whitelisted interface-version string candidates from both
the DLL and game executable (where the requested versions are often stored).
It exports no binary bodies, account IDs or machine paths and cannot install.

Save it from the Codex app into Downloads. Python 3 is already sufficient; Linux
can inspect the shared Windows game copy. With private paths selected:

    python3 ~/Downloads/mgsv-steam-capabilities.pyz \
      --game-dir "<copied game folder>" \
      --output ~/mgsv-steam-capabilities.json

This capture has already been received and accepted. No rerun is requested.
