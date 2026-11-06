# Remaining work in dependency order

The owner has since closed the Windows Sandbox. See the
[restart and development roadmap](ROADMAP.md) before running another QA helper:
the host cache may be reusable, but the old session-bound requests are stale.
The owner has confirmed the cache paths exist. The new
[restart packet](windows-restart.md) hashes the cache and coordinates a fresh
session locally; its first Windows run is the next owner action.

Target: Steam App 287700, regular 1.0.15.3, two players first; Windows primary,
Proton secondary. Every main mission, including Missions 1 and 46, prologue/variants,
all Side Ops and Free Roam is required, with no planned mission exclusions. Completion/rewards
must advance both isolated co-op saves. Regular Steam invitations are the intended
normal join flow; SteamID entry is acceptable as an interim/fallback method.
Neither path may depend on router port forwarding. Four players is a later extension.

Additional feasibility goal: support the current regular public Steam build.
Identify that build and assess its native/resource differences early; do not assume
the previously reported 1.0.15.4 is still current or run 1.0.15.3 hooks on it.
See [the compatibility assessment](current-version-feasibility.md). The restart
and baseline startup remain the immediate dependency.

1. **Finish local observability and its automated scorer.** Implemented in patch 0005:
   an opt-in, bounded atomic status-file publisher plus a read-only smoke runner.
   It is driven by actual Lua updates, with caller affinity, run/generation/frame
   IDs, independent native samples and stale-data rejection. See status-bridge.md.
   This verifies an observation channel, not co-op gameplay.
2. **Identify the installed Steam invite capabilities.** Completed: the supplied
   report matches the pinned game/DLL and all 12 required flat exports. Exact SDK
   signatures/callback layout were checked against pinned official Valve source.
   Both Windows gates passed: our synthetic cross-DLL fixture and the owner's real
   standalone Steam-context check. The latter initialized Steam, bound the expected
   interfaces, registered/unregistered the callback and shut down its own context.
   Actual delivery and the borrowed in-game context remain unverified. No rerun is
   requested for either standalone check.
3. **Implement Steam invite host/join control.** Add runtime host/guest/target state,
   invitation discovery/acceptance, private guest admission, deferred joining during
   loading and automatic mission selection. Handle warm and cold acceptance, the
   correct patched executable and local Fuse sidecar. Keep App 287700. Preserve the
   existing MGO invitation path. SteamID entry is acceptable for early measurements
   and as a fallback; ordinary Steam invitations remain the normal-flow goal.
   Verify the actual peer/relay transport separately, including two internet
   connections and restrictive NAT without router port forwarding. The current
   invitation components do not establish that connectivity contract.
   Patch 0006 now supplies flat binding, strict warm/cold intent parsing, a bounded
   callback queue and gated send/receive components tested with fake exports. It
   does not yet supply the friend picker, automatic FOX join/load, cold sidecar
   routing or verified MGO coexistence. Patch 0007 adds an inactive main-thread
   role/target controller with deferred loading, strict action acknowledgments and
   retained cleanup ownership. Its engine adapter/proof producer and legacy hook
   migration remain unfinished; production creates neither channel nor controller.
4. **Establish runtime save isolation and reversible installation.** AccountDir only
   directs backup/conversion writes; it does not redirect runtime saves. Confirm or
   implement safe routing/new test namespaces before launching an instrumented copy.
   Never use live userdata merely to test installation. Staging copies and backup
   existence are insufficient evidence of runtime isolation. A separate Windows
   login alone may still share the Steam installation/userdata; prove separate
   runtime storage and Cloud behavior before any real-game test. First check a
   separate Sandbox's boot, mapped-folder permissions and hardware DirectX11
   observations without Steam/game files or networking; see windows-isolation.md.
   The first attempt was blocked at launcher availability. After owner-approved
   feature enablement, the Sandbox harness passed all expected observations. A
   zero-host-mapping online Steam preparation profile is now packaged for approval;
   it installs/updates Steam only, ending at sign-in. That stage succeeded. The
   stable Input-RO/Output-RW profile's prelogin storage report is now accepted,
   with matching run/session and published source tag. The owner approved and
   completed guest sign-in to Library. The same-session offline cutoff receipt
   is accepted. A copy-only package now waits for a fresh guest cutoff receipt,
   stages ten known baseline files, and checks the separate guest copy. Its four
   receipt-validator tests passed; the owner then supplied matching receipts for
   all ten copied files. The first baseline startup helper is prepared and
   owner-approved; its three bounded validator checks passed. Offline licensing, runtime
   dependencies and game/save behavior remain pending. No game has run.
5. **Validate startup/resource contracts and synchronization.** Verify the actual
   Free Roam playable sequences, Normal/NormalScarf two-player dependencies and
   staged FPK companion routing. Implement session/mission/epoch-bound peer identity,
   liveness, complete initial state and agreed world center. Only then connect the
   existing default-inactive adapter to a real verification provider.
6. **Run automated Windows tests with two actual clients.** Start with the isolated
   single-client observation smoke, then host/guest invite acceptance, visibility,
   movement, world/enemy agreement, reload/travel/disconnect and stale-session cases.
   Bots/scorers drive and measure the game; owner playtesting is not the test plan.
7. **Add quest/progression authority and expand coverage.** Ordered, deduplicated
   host events and idempotent rewards for each co-op profile; all Side Ops, story
   missions, bosses, travel and special locations. Each supported case needs an
   automated positive run and meaningful negative/mutation controls.
8. **Proton compatibility, packaging, then optional four-player work.** Repeat the
   validated Windows behavior under Proton. Finish install/update/uninstall and
   launch handling; publish only when authorized. Four players requires another
   resource/allocation/authority review after two-player behavior is validated.

No real-game multiplayer tests have run. Cloud code tests and successful binary
builds do not change that status. Development QA packages are not an invitation to
install/run against the owner's live game or saves.
