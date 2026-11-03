# Windows test isolation before instrumented game runs

The real standalone Steam binding/registration result is accepted. No more
Steam capability captures are needed. Next establish a separate test OS and Steam
storage before an instrumented MGSV launch. A copied game folder/AccountDir is
not runtime save isolation, and the existing DYNAMITE save filenames can reuse
existing co-op progress. MGO filenames remain unchanged in upstream TppDefine.

## First prerequisite: offline Sandbox harness check

The separate ww-sandbox-check.exe uses only an already-installed Windows Sandbox.
It cannot enable optional features, install software, change firmware/security
settings, start Steam/MGSV or use accounts. Its candidate configuration requests
vGPU, 4 GiB guest RAM and disabled networking, clipboard/printer redirection and
microphone/camera input redirection.

Host preflight requires an existing system WindowsSandbox.exe, no observed running
Sandbox and sufficient memory for this harness (at least 8 GiB installed and 5 GiB
currently available). These checks do not guarantee Sandbox can boot.

The host creates a fresh nonce-labelled folder beside the helper, copies only its
own bounded/hash-checked executable into Input, holds that staged file locked,
maps Input read-only and maps only the new Output folder read/write. The parent Downloads folder,
Steam, user profiles and game folders are not mapped. It writes a WSB file and
starts the explicit system Sandbox executable. Existing Sandbox sessions are
left alone; no process is killed.

The automatic guest probe checks the expected executable path and default guest
username before writes, then checks a create-new input sentinel receives precisely
ACCESS_DENIED, own output/scratch empty-file writes/deletes, local adapter
observations and hardware D3D11 feature 11_0. A software DXGI adapter cannot satisfy
the graphics check. It makes no network request and releases all COM references.

The fixed 72-byte guest report is published atomically and bound to the host nonce
and staged helper hash. The host rejects stale/oversized/unknown/nonregular/reparse
reports and requires all observations for PASS. Launcher success cannot PASS.
JSON contains only statuses/booleans, the random run ID, our helper's hash and a
D3D result code, with no account IDs, user/computer paths, process lists or adapter
names/addresses. A missing guest report is TIMEOUT after 180 seconds.

These are harness observations, not VM attestation, proof of all network/host-drive
isolation, Steam/MGSV compatibility or runtime save isolation. Those fields remain
false even on PASS. Exact Windows configuration/runtime execution has not run in
the cloud. The first owner-run report was BLOCKED at launcher availability. After
the owner-approved feature change, the rerun is PASS with the expected helper hash
and all host/guest/mapping/scratch/adapter/hardware-D3D11 observations true. That
accepts the harness prerequisite, not save isolation or MGSV compatibility.

## Next prepared stage: Steam installation without login

[Steam preparation](steam-sandbox-preparation.md) defines a separate online profile
with no host mappings at all and disabled host clipboard/printer/mic/camera
redirection. It opens guest-local instructions and the official installer URL.
The owner reads and runs the provided guest-local verification commands before the
normal interactive installer. The bootstrapper must match the pinned Microsoft
WinGet SHA256 and pass Windows Authenticode validation. There is no silent install
or automatic license acceptance.

This stage needs owner approval for guest Steam installation and its self-updates.
It ends at the sign-in screen, without account login or game files. Since nothing
is mapped writable, there is no automatic guest report export. Same-session offline
control and game/report transfer remain unimplemented and must be designed before
credentials or game access. Closing this anonymous guest discards its setup.

## Later gates, not implemented by this prerequisite tool

1. Confirm guest boot and graphics observations. If the optional feature is
   unavailable, prepare its precise installation change for owner approval first.
2. Prepare a guest-only Steam installation and storage/account/Cloud procedure for
   review. Earlier account approval covered the standalone binding test, not a new
   installation/login or invitation sends.
3. Stage pinned compatible game files in guest-only storage. Never map live Steam
   userdata or original saves read/write.
4. Before the first game run, establish and verify a Cloud/network boundary that
   prevents uploads to account saves. An offline ephemeral guest is a candidate
   for the first observer smoke; actual Steam license/offline startup, game
   compatibility and this workflow remain unverified. Neither prior checker proves
   this step.
5. Run the existing automated single-client observation scorer inside that setup.
   Then characterize MGO routing, resources and the peer-bound handshake before
   any two-client invitation/gameplay test.

No game deployment, feature installation, new account use, publication or remote
PC access is authorized by this document.

Source references: pinned Dynamite
[TppDefine](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/moddata/standalone/TppDefine.lua)
and [save preparation](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/savebackup/savebackup.go).
Microsoft's [Sandbox overview](https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-overview)
and [configuration reference](https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file)
describe the platform/settings. Those live pages are blocked by this cloud's HTTP
policy, so exact candidate-configuration behavior still needs the guest result.
