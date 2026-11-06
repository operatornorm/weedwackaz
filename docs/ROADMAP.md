# Roadmap after the closed Windows Sandbox

Updated 7 November 2026 (Australia/Sydney).

## Current position

The source checkpoint is on `operatornorm/weedwackaz` main at
`3270b87cd1246e73097db8e9b5c612df1d024918`. All seven patches freshly reproduce
30 modified Dynamite source files; 181 portable checks passed. These are code
checks, not evidence of expanded co-op gameplay.

The owner closed Windows Sandbox. Its guest Steam installation, cached sign-in,
private session marker and guest-local game copy are gone. Windows Sandbox's
installation on the host is separate and does not need reinstalling merely
because a guest closed. Host-side downloaded tools, staged game files and reports
normally remain, but their presence must be checked on the owner's PC.

The previous reports remain historical evidence. They cannot establish storage,
network isolation or readiness for a new guest. The previously generated startup
ZIP is bound to the old run/session and must not be reused unchanged.

Target remains Windows-first Steam co-op, two players initially, both separate
co-op saves progressing, all main missions (1-50, plus prologue and variants),
all Side Ops and Free Roam. Every mission must be co-op playable in the completed
mod, including Missions 1 and 46, with no planned mission exclusions. Unresolved
mission blockers remain unfinished work. A Free Roam prototype does not narrow
this completion requirement. Proton and four players follow validated two-player Windows behavior.
Expanded gameplay is not yet implemented.

Regular Steam invitations are the intended normal join flow. Manual SteamID entry
is acceptable as an interim/fallback method. No router port forwarding is required:
this includes avoiding dependence on manual or automatic router port-mapping
configuration. Invitation delivery and actual game traffic are separate contracts;
both must be tested. Port-forwarding-free connectivity is a requirement, not a
verified capability of the current build.

Compatibility with the current regular Steam release is an additional feasibility
track. Development remains pinned to the identified 1.0.15.3 baseline until a
new-build profile is validated. See the
[source-backed compatibility assessment](current-version-feasibility.md).

## 1. Recover the host cache and make the workflow restartable

The owner confirmed that the old QA folder still has `Input/Game/mgsvtpp.exe`
and `Input/game-stage-manifest.json`. This establishes presence only. The new
coordinator rehashes all ten cached files against the accepted manifest before
opening a guest. No depot redownload is needed if that cache is intact.

The [restart coordinator](windows-restart.md) is now implemented and packaged.
It creates fresh run/session challenges, validates reports locally and exports
results before the guest closes. Fifteen focused checks passed and source review
found no remaining concrete blocker. Windows execution of the combined workflow
is pending. The complete packet is prepared before the owner opens a guest;
there is no cloud review round trip between each setup substep.

The next online preparation guest must initially map instructions/report folders
only. An old QA Input folder now containing game files must not simply be reopened
with its old online launcher. Make the game cache available only after the new
guest cutoff is checked. Keep prior reports as an archive, not current authority.

Exit condition: a verified reusable host cache and a reviewed fresh-session setup
packet that does not depend on keeping a guest open for days.

## 2. Establish one repeatable Windows startup

Use the already installed Sandbox for a short, complete baseline startup attempt
if it remains the quickest supported route. Its guest Steam installation and
owner sign-in must be recreated; original host Steam userdata must not be copied.
Prior approvals for that workflow and the first baseline startup remain recorded;
new run/session bindings are still required.

Before game access, check guest-private storage and the fresh offline boundary.
Then copy the verified baseline into guest-local storage and run the existing
bounded startup observer. Export its result immediately. No human playtest is
required; signing in and identifying a startup error are owner setup tasks.

Offline licensing and required Windows runtime components are unknown. If startup
needs activation or a component, diagnose that specific failure. Any legitimate
online activation path needs a reviewed Cloud/save boundary first; do not just
reconnect the staged guest, copy authentication state or bypass activation.

For repeated development, evaluate a persistent isolated Windows test installation
or VM. Prove game-compatible graphics, Steam storage separation and licensing
before adopting it. A new VM product or Windows installation is not authorized
merely by this roadmap. Do not promise that Sandbox itself preserves its guest.

Exit condition: reproducible game startup in an isolated setup, with known
component/licensing requirements and a tested shutdown/restart procedure.

## 2a. Assess the current Steam build early, in parallel

Reidentify the actual public executable and build ID; previously reported
1.0.15.4 is a historical candidate, not a verified latest-version label. Compare
native addresses/byte patches, object layouts, archive/script identities, Steam
interfaces and save behavior. Maintain explicit verified version profiles and
refuse unknown builds before running native hooks.

If a port is manageable, propose it before extensive mission-by-mission QA.
Otherwise document its concrete blockers and revisit priority. Validate one
new-build client, then two matching-build clients and the full regression matrix.
This secondary goal does not relax complete mission coverage or the network and
save requirements. The old host-cache check and restart work are unchanged.

## 3. Verify real runtime observations and save isolation

Run the opt-in observation build in the isolated test copy. Verify real frame
updates, lifecycle/sequence transitions, status-file freshness and native getter
behavior; all current stub tests are insufficient for these claims.

Establish where runtime saves actually go and protect original single-player and
existing co-op saves. `AccountDir` only redirects backup/conversion writes. Check
the MGO save namespace too. Determine a repeatable test-profile starting state.

Exit condition: usable real-game telemetry and verified isolated runtime storage.

## 4. Establish two-player transport and implement regular Steam invitations

Finish the FOX engine adapter and migrate legacy role/target hooks to the tested
in-memory controller. Bind the borrowed game Steam context safely, implement
friend selection and invite acceptance, and preserve the existing MGO path.
Handle both an already running game and acceptance while the game is closed,
launching the correct copied executable and required companion process.

First establish what the existing game transport actually provides. Verify
Steam-supported peer connectivity and relay fallback with the installed interfaces;
implement a transport adapter if the current path cannot meet the no-port-forwarding
requirement. An invitation UI alone cannot make an unsuitable transport work.

Use two Windows PCs with separate legitimately owning Steam accounts. The
networked lab needs its own verified Cloud/save safeguards; the offline startup
guest is not proof that invitations or relay transport work. Invite delivery is an
explicit test action. SteamID entry is allowed while ordinary invitations are
unfinished, so UI work need not delay the first real two-client measurements.
The normal finished invitation flow should join without entering connection data.

Automated bots/scorers then verify joining, peer identity, initial state, movement,
disconnect, reconnect and stale-session rejection in a small supported main-mission
scenario. Test PCs on different internet connections, without configured port
forwarding; verify relay fallback under restrictive NAT and record the observed
transport route. Same-LAN success is insufficient for that connectivity claim.

Exit condition for the first gameplay baseline: a measured two-client session,
permitting SteamID entry, with verified connectivity without port forwarding.
Regular Steam invite acceptance, including cold launch, remains a completion goal
and is required for the intended finished user experience.

## 5. Build one complete Free Roam and Side Op case

This is a focused integration milestone. Existing main-mission behavior must also
be regression-tested as these shared session/resource systems change.

Verify the real Free Roam sequence and package/resource contracts before enabling
the dormant adapter. Establish both realized players, shared world origin,
session/mission epochs, ownership and a complete initial state.

Start with one location and one Side Op. Cover enemies, interactions, hostages,
vehicles, extraction and travel, plus death/reload and a player dropping out.
Use the measured result to expand to the other regions and Side Op families.

Exit condition: the same complete scenario passes repeatable two-client tests,
including negative controls; removing a mission whitelist is not sufficient.

## 6. Advance both co-op saves and cover every main mission

Add host-authoritative quest events and ordered, deduplicated reward/progression
application to each player's separate co-op save. Test checkpoint recovery,
reconnect/replay and mission transitions without duplicate rewards or lost progress.

Maintain an explicit coverage matrix for main missions 1-50, prologue/variants and
all Side Ops. Include special locations, scripted sequences and bosses. For each
mission, characterize startup, player roles/spawn, scripted/cinematic transitions,
checkpoints and completion. Missions 1 and 46 carry the same complete-coverage
requirement as every other mission. Each case needs working resource/lifecycle
handling and automated evidence. Claim support only for cases actually tested;
unverified or failing missions remain open work, not accepted exclusions.

Exit condition: every required mission and Side Op is co-op playable, both
profiles advance correctly, all Free Roam regions are covered, and original saves
are protected. Partial coverage is an intermediate checkpoint, not completion.

## 7. Package, validate Proton, then consider four players

Produce reversible installation/update/uninstall and the intended regular Steam
invitation flow, retaining an optional SteamID fallback. Verify both joining paths
without required router port forwarding. Repeat the established Windows scenarios under Proton. Four-player
support needs a further resource/allocation, ownership and synchronization review
after two-player behavior is stable.

There is no reliable completion date yet. Complete mission coverage remains the
completion criterion; important unknown engine behavior still needs measurement
in a real game process.

## Checkpoint practice

- Commit tested source and public documentation to the project repository at
  meaningful milestones under the owner's publishing authorization.
- Keep game assets, saves, authentication state and private captures off GitHub.
- Retain host-side input caches and small result reports across guest shutdowns.
- Make active guest state expendable and validate each new boot independently.
- Finish and export each owner-run test in one sitting where possible.
- Preserve previous approvals; ask again only when an action adds genuinely new
  software, account/network scope or another material change.
