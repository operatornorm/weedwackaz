# weedwackaz

Development toward MGSV co-op across every story mission, all Side Ops and Free Roam.
Windows is primary, Proton secondary; two players first and four later. Both players'
co-op saves must receive completion and rewards. Dynamite v0.6.0 is the baseline.

Full coverage is not implemented or validated. Preliminary Windows and Linux
installers now build; a runtime registry capture has been cataloged privately.
No real-game co-op tests have run.

This repository preserves the development source as seven ordered patches against
[Dynamite v0.6.0](https://github.com/unknown321/dynamite/tree/7fe74d31128ed8d3741b07181cb99e4adc1f57be),
plus build scripts, tests, diagnostics and documentation. Game assets, saves,
account data, private captures and generated installers are excluded. The patches
retain Dynamite's [GPLv3 plus Commons Clause license](patches/DYNAMITE-LICENSE);
the embedded JSON helper retains its MIT notice in patch 0005.

To reconstruct the current patched source beside this checkout:

```bash
git clone https://github.com/unknown321/dynamite.git ../dynamite
git -C ../dynamite checkout 7fe74d31128ed8d3741b07181cb99e4adc1f57be
for patch in patches/000*.patch; do
    git -C ../dynamite apply "$PWD/$patch"
done
python3 build-support/export_invite_controller_patch.py --verify-only
```

Use a new source directory for these commands. They do not install anything into
the game. The verification checks all seven patches against 30 current source files.

- [Setup guide](docs/mgsv-coop.md)
- [Remaining tasks in dependency order](docs/NEXT-STEPS.md)
- [Full-coverage scope and next development gates](docs/full-coverage.md)
- [First Free Roam integration milestone](docs/free-roam-integration.md)
- [Passive native runtime observations](docs/runtime-observation.md)
- [Opt-in status bridge and smoke scorer](docs/status-bridge.md)
- [Steam invite requirement and current preflight](docs/steam-invites.md)
- [Targeted controller structure check](docs/controller-check.md)
- [Read-only archive metadata reporter](tools/mgsv-pack-report/README.md)
- [Source inventory](qa/coverage-inventory.json)
- [Read-only runtime collector](qa/README.md)
- [Preliminary source patch](patches/0001-dynamite-lifecycle-and-packet-bounds.patch)
- [Open issues and validation limits](BUGS.md)
- [Linux copied-game launch helper](tools/launch_mgsv_coop.py), preserving Steam's
  selected Proton command while selecting a separate game folder and prefix.

In the approved build image, prepare the pinned controller fixtures, then run the
core/collector checks against the patched source and the routing checks:

```bash
python3 build-support/check_allocation_expansion.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s tools -p 'test_launch_mgsv_coop.py' -v
```

Set DYNAMITE_SOURCE_DIR if the patched source is not beside this repository. Tests
require a host C++ compiler and Lua library, supplied by the approved build container.
The 4 November 2026 checkpoint passed all 181 checks with Lua 5.1.5
(173 core/collector checks and eight launcher checks). They use source modules
with engine stubs, portable native code and a stand-in process. They do not establish game compatibility or working co-op.
The corrected archive reporter separately passes 15 Go checks and a bounds mutation check.
A [copyable Python fallback](tools/mgsv-pack-report/TEXT-TRANSFER.md) avoids binary downloads.
The [allocation identity planner](tools/plan_free_roam_allocation.py) now accepts
the corrected metadata capture and rejects ambiguous or changed inputs. Its output
cannot be applied. All three stock controller structures now match. A profile-preserving
two-slot expansion and separate support-pack prototype pass native-reader checks.
The [dormant Free Roam adapter patch](patches/0003-dynamite-dormant-free-roam-adapter.patch)
now connects package selection, allocation, reload and teardown, with 22 Lua
regressions. Production activation remains disabled: native verification, resource
compatibility, staged application and a verified playable hook remain pending.
The passive native/Lua observation layer now reports bounded known/unknown state;
eight additional checks include the actual native binding in a real Lua VM and
two rejected mutations. It supplies no readiness receipt or automatic sampler.
The separate test-only status-file bridge now polls after normal updates when
explicitly enabled. It has caller/run/generation fencing, bounded atomic publication
and a scorer that rejects stale frames/native samples. Default native builds refuse
capture. The Steam capability report is accepted. Flat bindings, bounded callback
and invite protocol components now pass fake-Steam checks, and the owner-supplied
synthetic Windows DLL result is PASS. The new inactive session controller adds
in-memory roles/targets, deferred loading and retained cleanup ownership, with 15
additional checks including four rejected mutations. It has no production instance
or engine adapter. The owner's real standalone Steam-context check also passed
binding and callback registration/unregistration. Actual delivery and the borrowed
in-game context remain untested. Friend-selection UI, automatic
FOX joining and MGO coexistence remain unfinished; no real invite or gameplay success
is claimed. Runtime save isolation remains a blocker before game deployment.
The separate Sandbox boot/permission/DirectX11 check passed. Subsequent owner-run
reports accepted guest Steam setup, the offline cutoff and the matching ten-file
baseline game copy. The first offline baseline startup helper is prepared and
owner-approved; its Windows run has not been reported. It observes only the
copied game's startup, with no mod installation or multiplayer claim. See
[the current remaining tasks](docs/NEXT-STEPS.md). Generic QA script templates are
under [tools/windows-qa-session](tools/windows-qa-session); session-specific requests
and reports stay private.
