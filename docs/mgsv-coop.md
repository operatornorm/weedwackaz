# MGSV: The Phantom Pain co-op route

The broader project now targets every story mission, all Side Ops and Free Roam,
including completion/rewards for both co-op saves. This page describes the existing
official mod baseline only; see [development scope](full-coverage.md) for the unfinished
extension work and validation limits.

Research checked 2026-10-31. No mod installed and no game-client tests run.

## Recommended starting point

[Dynamite](https://github.com/unknown321/dynamite) is an early **two-player** co-op mod.
Use it as the baseline; four players are an optional future development milestone.
This is mission co-op from the mod's supported list, not full campaign/free-roam parity.

Target priority: **Windows first**, Linux/Proton second. Preparing files on Linux does
not change that priority. Windows readiness requires validation on Windows; Proton-only
results must be reported separately. Current work configures the existing official mod
rather than delivering a newly built custom co-op release.

Official requirements: a legitimate, unmodified **non-Japanese Steam copy**, Windows
10+ or Linux/SteamOS, Steam connectivity, and at least 1 GB free on the relevant drives.
The source documents Linux/SteamOS support; a mixed Windows/Proton session has not been
tested in this project. Sources: [README](https://github.com/unknown321/dynamite) and
[v0.6.0 user docs](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/webui/docs/docs.md).

## Before downloading or changing anything

Identify both game copies. The executable version and hash, Steam build ID, region,
OS and any Proton version matter. Do not send game executables, saves, account data
or credentials. The cloud workspace cannot inspect a game installed on another PC.

On Windows, Properties → Details for `mgsvtpp.exe` gives its file version. These
optional PowerShell commands are read-only; replace the placeholder locally:

```powershell
$exe = Get-Item -LiteralPath '<game dir>\mgsvtpp.exe'
$exe.VersionInfo.FileVersion
(Get-FileHash -LiteralPath $exe.FullName -Algorithm SHA256).Hash
```

The Steam build ID is in `<Steam library>\steamapps\appmanifest_287700.acf`:

```powershell
Select-String -LiteralPath '<Steam library>\steamapps\appmanifest_287700.acf' -Pattern '"buildid"'
```

On Linux, from a terminal in the game directory, these commands read the executable
without running or modifying it:

```bash
exiftool -FileVersion -ProductVersion mgsvtpp.exe
sha256sum mgsvtpp.exe
```

If ExifTool reports `Error processing PE resources`, this fallback can extract the
embedded version strings:

```bash
strings -e l mgsvtpp.exe | grep -A 1 -E '^(FileVersion|ProductVersion)$'
```

Record that the version came from strings rather than a successfully parsed version
resource. A matching version string does not replace the executable SHA-256.

Share only those version/hash/build values and whether the copy is the Japanese edition;
keep personal paths and account details private. No installation is authorized by these
read-only checks.

The requested [AGENTS.md](https://github.com/cranebeaker/coop-anything/blob/main/AGENTS.md)
requires preserving the original game install and saves, using isolated test copies, and
asking before installing tools, downloading large files, or using accounts. Prepare a
recoverable backup and isolated install/save setup before applying any mod or rollback.
Verify that Steam actually launches the isolated copy. The stock mod installer modifies
its selected game directory and creates copied saves in Steam userdata; that is not,
by itself, sufficient isolation. No such setup has been validated yet.

## Resolve compatibility first

The official README requires rollback because the June 2026 game update breaks the
released mod. The author's [issue #136](https://github.com/unknown321/dynamite/issues/136)
lists **depot 287701**, **build 6239679**, **manifest 2518831260221836800**.
The game's **AppID is 287700**. These IDs are different things. They have been recorded
from the issue, not verified against a game install. Some issue commenters report lack
of access to that depot; legitimate account entitlement must be checked before promising
a downgrade. Do not run download/rollback commands against the original install.

### Proposed rollback procedure for a 1.0.15.4 copy

These are local steps for a player operating their own Steam client. They have not
been performed by the cloud agent or tested as an installation here. Check available
space before starting. No Steam credentials need to be shared in chat. The playbook's
approval rule applies to actions an agent performs; it does not require asking an agent
for permission to follow these instructions yourself.

1. Record the original `mgsvtpp.exe` SHA-256 with the read-only command above. Keep
   game and save identity records in ignored/private notes. Preserve the original
   install and saves; do not point the mod installer at them.
2. In the legitimately owning Steam client's console, the AppID/depot/manifest tuple
   translates to:

   ```text
   download_depot 287700 287701 2518831260221836800
   ```

   Steam downloads depot content separately and prints its destination. Treat its
   actual output as the location; do not assume a platform-specific path or download
   size. If entitlement fails, stop rather than substituting another depot or account.
3. Inspect the downloaded executable version and SHA-256 before use. The expected
   old executable version is 1.0.15.3; stop and investigate a mismatch. A source-reported
   manifest/build ID is not proof of the executable version on disk.
4. Assemble an isolated test game copy using verified content. Do not copy old files
   over the ordinary Steam install. Confirm how Steam/Proton will launch this copy
   and where its Steam API save writes will go before installing or launching the mod.
   This launch/save isolation has not yet been established for a test machine.
5. Only after those checks, download the pinned official mod for the installer OS,
   verify its digest below, and install into the isolated setup. Repeat the compatible
   baseline on the second machine. Keep the local master server enabled.

The game download may be large, and preparing an isolated install needs additional
disk space. The mod's own 1 GB requirement is not a bound on either requirement.

### Linux Steam console steps

1. Close MGSV. Open the desktop Steam client, online and signed into the account that
   owns the regular game. Ensure there is space on Steam's own storage volume for
   an additional depot download; it may be substantial.
2. In a Linux terminal run `xdg-open 'steam://open/console'`. Accept opening Steam if
   prompted. A **Console** tab should appear in Steam. This uses the existing Steam
   installation, including its registered Flatpak handler where applicable.
3. Paste `download_depot 287700 287701 2518831260221836800` into Steam's console input
   and press Enter. This is a Steam console command, not a Linux shell command.
4. Keep Steam running. Wait for a `Depot download complete` message and its destination
   path. The transfer may not appear in the ordinary Downloads view. If Steam reports
   an error instead, record the exact error and stop before modifying any game files.
5. Open the destination printed by Steam in Thunar and locate its `mgsvtpp.exe`.
   Open a terminal in that downloaded executable's directory and run:

   ```bash
   strings -e l mgsvtpp.exe | grep -A 1 -E '^(FileVersion|ProductVersion)$'
   sha256sum mgsvtpp.exe
   ```

   The expected old version is 1.0.15.3. Record the result and stop on a mismatch.
   Do not overwrite the ordinary installed game or run the mod installer yet: this
   completes only the download and identity check, not the isolated install setup.

A [third-party fork commit](https://github.com/slimy-bro/dynamite-vibecoded/commit/42806d1f1a182763b8809bccf3cbca37a8045e51)
claims 1.0.15.4 support. Its own
[porting notes](https://github.com/slimy-bro/dynamite-vibecoded/blob/42806d1f1a182763b8809bccf3cbca37a8045e51/docs/PORTING.md)
still require two-player testing and updated-script comparison, and the installer
accepts an unknown stock archive checksum. Its releases page lists no builds, and its
README download points to the original release. It is **not a verified ready-to-play
alternative**. Do not relax checksum verification to make it install.

## Pinned official downloads, once prerequisites are satisfied

Official release: [v0.6.0](https://github.com/unknown321/dynamite/releases/tag/v0.6.0),
source commit `7fe74d31128ed8d3741b07181cb99e4adc1f57be`.

| Asset | Published SHA-256 |
|---|---|
| [Windows](https://github.com/unknown321/dynamite/releases/download/v0.6.0/dynamite-windows-amd64.exe) | `08762dff3f3f790af0b340c38bcb295dc2e78ae34bf4353479e10c1cd20c22d3` |
| [Linux](https://github.com/unknown321/dynamite/releases/download/v0.6.0/dynamite-linux-amd64) | `19696deb3255ae9ad07b0bec7294b0a6a83faa2f1d05c87c2e08dd6658f51d86` |

These are digests from GitHub's official release asset metadata, not hashes of binaries
downloaded here. Verify the actual downloaded file before running it. Use the installer
for the OS running it; the game itself runs through Proton on Linux.

### Linux staging preflight

After Steam reports the entire depot download complete, preserve that clean download
and use a separate copy as the mod workspace. Open a terminal in that test copy's root,
the directory containing its 1.0.15.3 `mgsvtpp.exe`, and run:

```bash
md5sum master/0/00.dat
```

The [official v0.6.0 installer source](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/installer/installer.go)
expects `2779dcc79b7b700ed70b3900344cc164`. A missing file or mismatch needs investigation;
do not bypass this check or verify the isolated old copy through Steam in a way that
replaces it with the current build. This single-file check does not prove depot completeness.

Download the versioned Linux mod asset above, place it in the test game directory,
and verify it without running it:

```bash
sha256sum dynamite-linux-amd64
```

Compare against the full published digest in the table. Runtime launch instructions
depend on the local Steam setup (native package versus Flatpak), the test directory
and filesystem, and the chosen Proton version.

The release's `Install()` starts by copying saves and then validates `00.dat`.
Its [save-copy implementation](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/savebackup/savebackup.go)
backs up `287700` and `311340` under the configured account directory and adds
`DYNAMITE_*` files in their local/remote subdirectories. It does not derive that save
location from the copied game folder. Establish the save backup/isolation plan before
launching an installation; game-directory isolation alone is insufficient.

## Native Linux Steam: launch the copied game

The [launch helper](../tools/launch_mgsv_coop.py) preserves Steam's selected Proton
command and changes its single `mgsvtpp.exe` argument to the supplied co-op copy. It
sets the working directory, native `dinput8.dll` override, and a separate prefix under
`~/.local/share/mgsv-coop/compatdata`. It requests exposure of the copied directory to
the runtime via `STEAM_COMPAT_INSTALL_PATH` and `STEAM_COMPAT_MOUNTS`. Integration
with a real Steam/Proton game client has not been tested here.

The prefix is separate; **Steam account userdata is still shared**. Before installing
or launching, fully exit Steam and copy its `287700` and `311340` account subdirectories
to an independent backup. If either is missing, resolve that before installing. Do not
edit the original `TPP_*` or `PERSONAL_DATA` saves. Backups are not proof of isolation;
verify original-save hashes after any test run.

1. Save the helper outside the normal installation, for example in the co-op workspace's
   parent folder. It requires Python 3, not executable permission.
2. Verify the pinned Linux Dynamite asset's SHA-256 against the table above. If saved
   as `~/Downloads/dynamite-linux-amd64`, mark it executable, open a terminal **in the
   co-op game copy**, and start it:

   ```bash
   chmod u+x "$HOME/Downloads/dynamite-linux-amd64"
   "$HOME/Downloads/dynamite-linux-amd64"
   ```

   Keeping this native binary on the Linux drive avoids relying on executable
   permission for it on a shared Windows partition.
3. Its UI normally opens at `http://127.0.0.1:8070`. **Account Directory** is the
   numbered account folder under native Steam's `~/.steam/steam/userdata`, not the
   `287700` subdirectory. Inspect that selection. Keep **Use Local Master Server**
   enabled, choose Host mode or enter the host's Steam profile, and use a host whitelist.
4. Once the backup and selected paths are correct, **Save configuration** installs in
   the current working directory and adds Dynamite saves in the configured account
   directory. Wait for success; keep the installer running for its local master server.
5. Reopen Steam, select the desired Proton in MGSV's Compatibility settings, and save
   any prior Launch Options text before replacing it with this template:

   ```text
   python3 "<helper path>/launch_mgsv_coop.py" --game-dir "<co-op game dir>" --expected-sha256 <recorded 1.0.15.3 SHA-256> -- %command%
   ```

   The helper sets the DLL override and prefix itself. It refuses ambiguous routing,
   a mismatched executable hash, conflicting dinput8 settings, a missing mod DLL,
   or reuse of the inherited normal Proton prefix.
6. Launch through MGSV's regular Steam entry. For a routing-only check first, add
   `--dry-run` immediately before `-- %command%` and append
   `> "$HOME/mgsv-coop-launch-check.txt" 2>&1`. Steam returns without launching the
   game. Check that private output; remove the dry-run flag and redirection for a
   real launch after confirming the selected paths.

A real launch writes `~/.local/share/mgsv-coop/last-launch.json` and enables Proton
logs under `~/.local/share/mgsv-coop/logs`. The record describes the requested routing;
it does not prove which exe ultimately ran, prevent Steam-API relaunches, or prove
game/save correctness. Keep logs private. A copied game on NTFS may still encounter
filesystem/runtime issues; a Linux-home prefix alone cannot rule those out.

Eight stand-in-process tests passed for routing, argument preservation, separate
prefixes, guards and dry-run behavior. No MGSV, Steam-client, Windows or co-op game
tests have run here. Restore the prior Launch Options to return to the usual Steam
route. The helper does not edit the normal game or Proton Experimental.

Windows uses the official Windows Dynamite executable. This helper is only for the
secondary Linux/Proton route; native Windows validation remains required.

## Host/join flow after a validated isolated installation

This summarizes the pinned user docs; it has not been exercised here.

1. Both players use the same compatible game/mod baseline. Keep Dynamite's bundled
   **local master server** enabled and its process running. It redirects co-op records
   away from the original game service. Use a host whitelist for the intended friend.
2. Configure one player as host and the other with that host's Steam profile/SteamID.
   Configure the copied save/account location only after isolation is established.
3. Linux/SteamOS launch option documented by the author:
   `WINEDLLOVERRIDES="dinput8.dll=n,b" %command%`.
4. Choose a mission from the installed mod's supported mission list. The host loads it
   and waits until the character is visible, past the mission splash screen.
5. The guest holds the Master key, default **V**, then presses **Up** to connect.
   After `Connection established`, the guest starts the same mission. Repeat the
   connection step for every mission.
6. If disconnected, the documented reset is Master key + **Left**. Avoid restarting
   from the pause menu, which the docs say causes an infinite loading screen.

Known limitations include invisible players/hostages, enemy and vehicle desync,
mission-script failures, and crashes. Fultoning a partner fails the mission. Progress
uses separate copied saves; ordinary online resources are not transferred. Treat this
as an experimental co-op mod, not a tested full-campaign conversion.

## Validation and later four-player work

No game-level QA has run. Before claiming compatibility, automate a two-client baseline
on isolated copies: connection, both players visible/moving, enemy damage/objectives,
mission finish, reconnect, and verification that original saves/install were unchanged.
Repeat with a Windows host/Proton guest and the reverse if mixed-OS play is required.
The playbook calls for bots driving real clients, not asking players to serve as QA.

The author's [16-player notes](https://github.com/unknown321/dynamite/blob/master/docs/MAKING_OF.md#16-player-support)
say more than two players failed to start. Four-player support needs development and
four-client QA. [Joint Operations](https://github.com/Hound-Protocol/Joint-Operations)
plans larger sessions but currently says "Nothing is playable yet." No four-player
build was verified in the sources checked.

Public research corrections are also prepared locally in the `coop-anything` checkout.
No accounts were used to publish, no issue/PR was opened, and no environment was published.
