# Guest-only Steam preparation for review

The offline Sandbox prerequisite passed. The next package is
build-artifacts/steam-sandbox-preparation/Steam-sandbox-preparation-v2.zip.
The owner explicitly approved guest Steam installation and self-updates.
Windows execution is pending; the cloud has not launched the profile.

The new profile enables networking, requests vGPU/4 GiB RAM, disables host
clipboard/printer/microphone/camera redirection and declares **no host folder
mappings**. It leaves the existing offline prerequisite profile unchanged.
Closing an existing Sandbox discards its contents; the new profile needs a fresh
guest, not an edit applied to a running instance.

Guest startup checks the expected Windows guest identity, writes a readable
instructions file to its own Desktop using create-new semantics, and opens
Notepad plus the official SteamSetup URL in the guest browser. Instructions are
encoded as data for command-line transport and never evaluated at startup.
Complete readable logon source and instructions accompany the profile.

After approval, the owner downloads SteamSetup inside the guest browser. The
provided commands, copied locally within the guest into its Windows PowerShell,
require exact SHA256 and a Valid Windows Authenticode result before opening the
normal interactive installer. The whole pasted block is one invocation so any
guard error stops before installer launch. Windows execution policy and browser/security checks
are unchanged. No silent installation or automatic license acceptance is used.

Installer metadata is independently pinned from official Microsoft WinGet:

- Package Valve.Steam 2.10.91.91, official Valve HTTPS installer URL.
- WinGet commit9005e96b4e208d3332cd49b26540be4557d8a268.
- Manifest SHA256 abc277fcc4b5f99b40cbc990caa9f75ee5e30bf59d42ef3af00bffd3c3128030.
- Installer SHA256 7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb.

See [pin metadata](../qa/steam-installer-pin.json) and the
[pinned Microsoft manifest](https://github.com/microsoft/winget-pkgs/blob/9005e96b4e208d3332cd49b26540be4557d8a268/manifests/v/Valve/Steam/2.10.91.91/Valve.Steam.installer.yaml).
The URL can change content: mismatches must stop; no new hash is learned or
signature check bypassed. SteamSetup has not been downloaded/executed in cloud.
Steam's later self-updates use Valve's normal verification and can download
hundreds of MB or more; they are outside this bootstrapper pin and explicitly
included in the requested approval.

The stage ends at Steam's sign-in screen. No account login, credentials, game
installation or launch is requested. No screenshots or Steam logs are collected.
There is no automatic report export because there is no writable host share;
the owner reports whether installation reached sign-in or its preparation error.
This is installation setup, not a game playtest or gameplay QA result.

Same-session offline control, authenticated startup and report/game transfer are
separate unfinished gates before login or game files. This package does not
claim save isolation or MGSV/co-op compatibility. It may be kept open to continue
immediately, but closing Sandbox discards this anonymous installation/update.

Five targeted generator checks passed, including the single-invocation guard: zero mappings/redirect policy, complete
encoded-source/data roundtrips, refusing existing output, and rejecting invalid
pins/endpoints. These are code checks, not Windows execution of the new profile.
