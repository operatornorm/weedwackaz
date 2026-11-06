"""Build a local, owner-reviewed Windows Sandbox restart packet; execute nothing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

import check_game_stage
from prepare_steam_sandbox import load_pin


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "tools/windows-qa-session"
OUTPUT = ROOT / "build-artifacts/windows-qa-restart"
PHASE_FILES = ("GUEST-SESSION.txt", "Guest-Prelogin.txt", "GUEST-OFFLINE.txt",
               "GUEST-STAGE.txt", "GUEST-STARTUP.txt", "START-HERE.txt")
PROOF_FLAGS = frozenset(("executed_source_attested", "all_archives_stock_verified",
                         "save_isolation_verified", "offline_license_verified",
                         "game_launched", "launch_authorized", "co_op_verified"))
ACCEPTED_KEYS = frozenset(("schema", "result", "run_id", "guest_session_id",
                           "challenge", "files", "bytes")) | PROOF_FLAGS
CUTOFF_MARKER = "    # This is a point-in-time local policy/adapter observation"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def identifier(value, size):
    return (isinstance(value, str) and re.fullmatch("[0-9a-f]{%d}" % size, value)
            and value != "0" * size)


def validate_cache(manifest_raw, accepted_raw, cache_run, manifest_sha256):
    """Validate a previously accepted ten-file cache without opening game files."""
    if not identifier(cache_run, 32) or not identifier(manifest_sha256, 64):
        raise ValueError("invalid expected cache identity")
    if not isinstance(manifest_raw, bytes) or sha256(manifest_raw) != manifest_sha256:
        raise ValueError("cache manifest hash changed")
    manifest = check_game_stage.decode(manifest_raw)
    accepted = check_game_stage.decode(accepted_raw)
    if not isinstance(manifest, dict) or set(manifest) != check_game_stage.BASE_KEYS:
        raise ValueError("invalid cache manifest schema")
    if type(manifest["schema"]) is not int or manifest["schema"] != 1 or manifest["stage"] != "game-stage-v1":
        raise ValueError("invalid cache manifest phase")
    for key, size in (("run", 32), ("session", 32), ("challenge", 32), ("source_tag", 64)):
        if not identifier(manifest[key], size):
            raise ValueError("invalid cache manifest identity")
    if manifest["run"] != cache_run:
        raise ValueError("wrong accepted cache run")
    files = check_game_stage.files(manifest["files"])
    if not isinstance(accepted, dict) or set(accepted) != ACCEPTED_KEYS:
        raise ValueError("invalid accepted cache schema")
    if (type(accepted["schema"]) is not int or accepted["schema"] != 1
            or accepted["result"] != "copy_observations_accepted"
            or accepted["run_id"] != cache_run
            or accepted["guest_session_id"] != manifest["session"]
            or accepted["challenge"] != manifest["challenge"]):
        raise ValueError("stale accepted cache identity")
    if (type(accepted["files"]) is not int or accepted["files"] != len(files)
            or type(accepted["bytes"]) is not int
            or accepted["bytes"] != sum(size for size, digest in files.values())):
        raise ValueError("accepted cache totals differ")
    if any(accepted[key] is not False for key in PROOF_FLAGS):
        raise ValueError("accepted cache contains unsupported proof claims")
    return manifest


def inner_block(text):
    if not text.startswith("& {\n") or not text.endswith("\n}\n"):
        raise ValueError("reviewed component must contain one outer paste block")
    return text[4:-2]


def tail_body(text):
    if not text.endswith("\n}\n"):
        raise ValueError("reviewed tail is missing its final brace")
    return text[:-2]


def replace_output(text, old, new):
    old_line = "    Write-Output '" + old + "'"
    if text.count(old_line) != 1:
        raise ValueError("reviewed component handoff changed")
    return text.replace(old_line, "    Write-Output '" + new + "'")


def guest_session(prelogin, offline, stage_tail, startup_tail, pin):
    # Reviewed component bodies remain literal PowerShell. They are never read
    # as executable data, dot-sourced, or evaluated by the generated session.
    initial = r"""& {
    $ErrorActionPreference = 'Stop'
    Set-StrictMode -Version 2.0
    $mgsvIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ($mgsvIdentity -notmatch '\\WDAGUtilityAccount$') { throw 'Run only INSIDE the new Windows Sandbox.' }
    if ($PSDefaultParameterValues.Count -ne 0 -or $global:PSDefaultParameterValues.Count -ne 0) { throw 'Use a fresh powershell.exe -NoLogo -NoProfile guest shell.' }
    if (Microsoft.PowerShell.Utility\Get-Variable -Name PSSenderInfo -ValueOnly -ErrorAction SilentlyContinue) { throw 'Use a local guest shell.' }
    $mgsvPrincipal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $mgsvPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Open Administrator Windows PowerShell INSIDE the guest.' }
    $mgsvInput = 'C:\MGSVQA\Input'
    $mgsvOutput = 'C:\MGSVQA\Output'
    if ((Microsoft.PowerShell.Management\Get-Item -LiteralPath "$mgsvInput\run.json").Length -gt 2048) { throw 'Oversized run manifest.' }
    $mgsvRun = Microsoft.PowerShell.Management\Get-Content -LiteralPath "$mgsvInput\run.json" -Raw | Microsoft.PowerShell.Utility\ConvertFrom-Json
    if ($mgsvRun.schema -ne 1 -or $mgsvRun.run -cnotmatch '^[0-9a-f]{32}$' -or $mgsvRun.run -eq ('0' * 32) -or $mgsvRun.session_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid fresh run manifest.' }
    $mgsvSessionSource = (Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath "$mgsvInput\GUEST-SESSION.txt" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($mgsvSessionSource -cne $mgsvRun.session_sha256) { throw 'Merged guest instructions changed.' }
    if ((Microsoft.PowerShell.Management\Test-Path -LiteralPath "$mgsvInput\Game") -or (Microsoft.PowerShell.Management\Test-Path -LiteralPath "$mgsvInput\game-stage-manifest.json")) { throw 'Game data appeared before the fresh offline gate.' }
    function Wait-MgsvHostFile($mgsvWaitName) {
        $mgsvWaitClock = [Diagnostics.Stopwatch]::StartNew()
        $mgsvWaitPath = Join-Path $mgsvInput $mgsvWaitName
        while (-not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $mgsvWaitPath)) {
            if (Microsoft.PowerShell.Management\Test-Path -LiteralPath "$mgsvInput\host-error.json") { throw 'The host stopped this run. Read the host console; keep the guest open.' }
            if ($mgsvWaitClock.Elapsed.TotalMinutes -gt 60) { throw 'Timed out waiting for the host. Keep the guest open and read the host console.' }
            Microsoft.PowerShell.Utility\Start-Sleep -Seconds 2
        }
        if (Microsoft.PowerShell.Management\Test-Path -LiteralPath "$mgsvInput\host-error.json") { throw 'The host stopped this run. Read the host console; keep the guest open.' }
    }
    function Copy-MgsvRestartStream($mgsvReadStream, $mgsvWriteStream, [long]$mgsvExpectedBytes, $mgsvLabel) {
        $mgsvBuffer = [byte[]]::new(4MB)
        $mgsvCopied = [long]0
        $mgsvProgressClock = [Diagnostics.Stopwatch]::StartNew()
        $mgsvLastProgress = [long]-1000
        try {
            while (($mgsvReadCount = $mgsvReadStream.Read($mgsvBuffer, 0, $mgsvBuffer.Length)) -gt 0) {
                $mgsvWriteStream.Write($mgsvBuffer, 0, $mgsvReadCount)
                $mgsvCopied += $mgsvReadCount
                if ($mgsvCopied -gt $mgsvExpectedBytes) { throw 'Game source grew during copy.' }
                if (($mgsvProgressClock.ElapsedMilliseconds - $mgsvLastProgress) -ge 1000) {
                    $mgsvLastProgress = $mgsvProgressClock.ElapsedMilliseconds
                    Write-Progress -Id 1 -Activity ('Guest copy: ' + $mgsvLabel) -Status ('{0:N0} / {1:N0} bytes' -f $mgsvCopied, $mgsvExpectedBytes) -PercentComplete ([int](100.0 * $mgsvCopied / $mgsvExpectedBytes))
                }
            }
            if ($mgsvCopied -ne $mgsvExpectedBytes) { throw 'Game source ended before its expected byte count.' }
        } finally { Write-Progress -Id 1 -Activity ('Guest copy: ' + $mgsvLabel) -Completed }
    }
    Write-Output 'The official Steam download opens in the GUEST browser. Save SteamSetup.exe to this guest Downloads folder without running it.'
    Microsoft.PowerShell.Management\Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList '__STEAM_URL__'
    $mgsvAnswer = Read-Host 'Type DOWNLOADED after the guest browser has finished saving SteamSetup.exe, or STOP to abort'
    if ($mgsvAnswer -cne 'DOWNLOADED') { throw 'Owner stopped before installer execution.' }
    $mgsvSteamInstaller = Join-Path $env:USERPROFILE 'Downloads\SteamSetup.exe'
    if ((Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $mgsvSteamInstaller -Algorithm SHA256).Hash.ToLowerInvariant() -cne '__STEAM_SHA256__') { throw 'Steam installer hash mismatch. Do not run it.' }
    if ((Microsoft.PowerShell.Security\Get-AuthenticodeSignature -LiteralPath $mgsvSteamInstaller).Status.ToString() -ne 'Valid') { throw 'Steam installer signature is not valid.' }
    $mgsvInstallerProcess = Microsoft.PowerShell.Management\Start-Process -FilePath $mgsvSteamInstaller -PassThru
    try { $mgsvInstallerProcess.WaitForExit() } finally { $mgsvInstallerProcess.Dispose() }
    Write-Output 'Complete the normal guest Steam installer at C:\Program Files (x86)\Steam and allow its normal updates. Stop at Steam sign-in. DO NOT SIGN IN YET.'
    $mgsvAnswer = Read-Host 'Type SIGNIN only when the guest Steam sign-in screen is visible, or STOP to abort'
    if ($mgsvAnswer -cne 'SIGNIN') { throw 'Owner stopped before prelogin checks.' }
""".replace("__STEAM_URL__", pin["installer_url"]).replace("__STEAM_SHA256__", pin["installer_sha256"])
    prelogin_body = replace_output(inner_block(prelogin),
        "Prelogin observations saved. Return prelogin.gate and wait before signing in.",
        "Prelogin observations saved. Waiting for the local host validator before sign-in.")
    accepted_wait = r"""    Wait-MgsvHostFile 'prelogin-accepted.json'
    Wait-MgsvHostFile 'offline-request.json'
    if ((Microsoft.PowerShell.Management\Get-Item -LiteralPath "$mgsvInput\prelogin-accepted.json").Length -gt 2048 -or (Microsoft.PowerShell.Management\Get-Item -LiteralPath "$mgsvInput\offline-request.json").Length -gt 2048) { throw 'Oversized host acknowledgment.' }
    $mgsvAccepted = Microsoft.PowerShell.Management\Get-Content -LiteralPath "$mgsvInput\prelogin-accepted.json" -Raw | Microsoft.PowerShell.Utility\ConvertFrom-Json
    $mgsvNextOffline = Microsoft.PowerShell.Management\Get-Content -LiteralPath "$mgsvInput\offline-request.json" -Raw | Microsoft.PowerShell.Utility\ConvertFrom-Json
    if ($mgsvAccepted.schema -ne 1 -or $mgsvAccepted.result -cne 'prelogin_observations_accepted' -or $mgsvAccepted.run -cne $mgsvRun.run -or $mgsvAccepted.session -cne [IO.File]::ReadAllText('C:\MGSVQA\session.id') -or $mgsvAccepted.source_tag -cne $mgsvRun.session_sha256 -or $mgsvAccepted.offline_challenge -cnotmatch '^[0-9a-f]{32}$') { throw 'Wrong prelogin acknowledgment.' }
    $mgsvOfflineSource = (Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath "$mgsvInput\GUEST-OFFLINE.txt" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($mgsvNextOffline.schema -ne 1 -or $mgsvNextOffline.stage -cne 'offline-v1' -or $mgsvNextOffline.run -cne $mgsvAccepted.run -or $mgsvNextOffline.session -cne $mgsvAccepted.session -or $mgsvNextOffline.challenge -cne $mgsvAccepted.offline_challenge -or $mgsvNextOffline.source_tag -cne $mgsvOfflineSource) { throw 'Wrong offline request before login.' }
    Write-Output 'Host prelogin checks accepted. INSIDE guest Steam, sign in normally using your own Steam and Guard prompts. Do not paste credentials here.'
    Write-Output 'Disable Steam Cloud for MGSV in its guest Properties. Choose Steam Go Offline and restart in Offline Mode. Then choose Steam Exit and wait for Steam to close.'
    $mgsvAnswer = Read-Host 'Type OFFLINE after guest Steam Cloud is off, Offline Mode was entered, and Steam has exited, or STOP to abort'
    if ($mgsvAnswer -cne 'OFFLINE') { throw 'Owner stopped before network cutoff or game staging.' }
"""
    offline_body = replace_output(inner_block(offline),
        "Guest network cutoff recorded. Keep this guest offline. Return offline.gate and offline-request.json before any game staging.",
        "Guest network cutoff recorded. Keep this guest offline. Waiting for the local host validator.")
    stage_body = replace_output(tail_body(stage_tail),
        "Return only game-stage-result.json and game-stage-manifest.json to the chat.",
        "Waiting for the local host validator before the startup request.")
    old_copy = "$mgsvRead.CopyTo($mgsvWrite)"
    if stage_body.count(old_copy) != 1:
        raise ValueError("reviewed stage copy operation changed")
    stage_body = stage_body.replace(old_copy,
        "Copy-MgsvRestartStream $mgsvRead $mgsvWrite $mgsvEntry.bytes $mgsvEntry.path")
    old_wait = '    while (-not (Test-Path -LiteralPath "$mgsvInput\\game-stage-manifest.json")) {\n'
    if stage_body.count(old_wait) != 1:
        raise ValueError("reviewed stage wait changed")
    stage_body = stage_body.replace(old_wait, old_wait
        + '        if (Test-Path -LiteralPath "$mgsvInput\\host-error.json") { throw \'The host stopped this run. Read the host console.\' }\n')
    startup_body = replace_output(tail_body(startup_tail),
        "Return only startup-result.json and startup-request.json, plus any on-screen game error wording.",
        "The host will validate startup-result.json locally. Note any on-screen game error wording.")
    old_observe = "        while (-not $mgsvProcess.WaitForExit(1000) -and $mgsvClock.Elapsed.TotalSeconds -lt 120) { }"
    if startup_body.count(old_observe) != 1:
        raise ValueError("reviewed startup observation loop changed")
    startup_body = startup_body.replace(old_observe, """        while (-not $mgsvProcess.WaitForExit(1000) -and $mgsvClock.Elapsed.TotalSeconds -lt 120) {
            Write-Progress -Id 2 -Activity 'Guest startup observation' -Status ('{0:N0} / 120 seconds' -f $mgsvClock.Elapsed.TotalSeconds) -PercentComplete ([int][Math]::Min(100, 100.0 * $mgsvClock.Elapsed.TotalSeconds / 120))
        }""")
    startup_body = startup_body.replace("    } finally {\n        if ($mgsvProcess) {",
        "    } finally {\n        Write-Progress -Id 2 -Activity 'Guest startup observation' -Completed\n        if ($mgsvProcess) {")
    return (initial + "    # BEGIN reviewed prelogin component\n" + prelogin_body
            + "    # END reviewed prelogin component\n" + accepted_wait
            + "    # BEGIN reviewed offline component\n" + offline_body
            + "    # END reviewed offline component\n"
            + "    Wait-MgsvHostFile 'stage-request.json'\n"
            + "    Test-MgsvFirewall\n    Test-MgsvSteamClosed\n"
            + "    if (@(NetAdapter\\Get-NetAdapter -IncludeHidden | Where-Object { $_.Status.ToString() -eq 'Up' }).Count -ne 0) { throw 'Guest adapter changed before staging.' }\n"
            + "    # BEGIN reviewed stage component\n" + stage_body
            + "    # END reviewed stage component\n"
            + "    Wait-MgsvHostFile 'startup-request.json'\n"
            + "    # BEGIN reviewed startup component\n" + startup_body
            + "    # END reviewed startup component\n}\n")


START_HERE = """MGSV Windows QA restart packet — read all files before proceeding

This packet restarts a disposable Sandbox after the old guest was closed.
Keep the saved QA Input/Game and Input/game-stage-manifest.json together on your
Windows host. They must belong to the previously accepted cache. No game files,
account data, installer or credentials are included in this packet.

1. Extract the entire ZIP to a new folder. Read the ENTIRE HOST-RESTART.txt and
   GUEST-SESSION.txt, including all guards, waits and cleanup. Review the other
   source-tag TXT files too. Do not run any downloaded script file.
2. On your normal Windows desktop, open a fresh local Windows PowerShell with
   powershell.exe -NoLogo -NoProfile. Read and paste the WHOLE HOST-RESTART.txt
   & { ... } block once. Select GUEST-SESSION.txt when the file picker opens.
   The host locates the saved QA cache in its original Downloads run folder.
3. Keep the host console open. In the new Sandbox, open a fresh LOCAL guest
   Administrator Windows PowerShell with powershell.exe -NoLogo -NoProfile.
   Read GUEST-SESSION.txt in full and paste its WHOLE single & { ... } block
   once. Keep that guest console open through every phase; do not paste the
   separate source-tag components. No script policy change is required.
4. Follow the guest prompts for official Steam browser download, verified
   interactive installation, sign-in only after host prelogin acceptance,
   Cloud off, Offline Mode and Steam Exit. Any answer other than the exact
   requested word aborts. The startup READY/STOP prompt records an abort.
5. The host checks each bounded report locally before issuing the next request.
   Initial Input contains no game data. The host only stages its verified cache
   after fresh offline and prestage gates. The guest copies those files to its
   own C: drive. Wait for the HOST final restart-result.json report, then exit
   guest Steam. Once both helpers finish, you may close Sandbox; the host cache
   and report survive. Upload only restart-result.json and any game error wording.

Only this packet, a fresh Input folder and the writable Output report folder
are shared. Clipboard, printer, camera and microphone redirection are disabled.
The Output folder is writable host storage: keep Steam and game storage inside
the guest at the stated default paths. Steam updates use Valve's normal checks;
the SHA pin covers the bootstrapper, not Steam's later client downloads.

These are local observations, not executed-source attestation, stock verification
of all archives, license/save-isolation proof, gameplay or co-op verification.
The 120-second startup probe may report an early exit or missing component;
record its visible wording without installing anything or reconnecting the guest.
Do not send credentials, Guard codes, account files, screenshots or Steam logs.
"""


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def read_cache_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(8193)
    if len(raw) > 8192:
        raise ValueError("oversized cache JSON")
    return raw


def generate(output, manifest_path, cache_run, manifest_sha256, source_dir=SOURCES, pin_path=None):
    """Create readable files and a deterministic ZIP, refusing existing output."""
    output, manifest_path, source_dir = Path(output), Path(manifest_path), Path(source_dir)
    manifest_raw = read_cache_json(manifest_path)
    manifest = validate_cache(manifest_raw, read_cache_json(manifest_path.with_name("accepted.json")),
                              cache_run, manifest_sha256)
    pin = load_pin() if pin_path is None else load_pin(pin_path)
    prelogin = (source_dir / "Guest-Prelogin.txt").read_text(encoding="utf-8")
    offline = (source_dir / "GUEST-OFFLINE.txt").read_text(encoding="utf-8")
    stage_tail = (source_dir / "GUEST-STAGE.tail.txt").read_text(encoding="utf-8")
    startup_tail = (source_dir / "GUEST-STARTUP.tail.txt").read_text(encoding="utf-8")
    if offline.count(CUTOFF_MARKER) != 1:
        raise ValueError("reviewed offline cutoff marker changed")
    prefix = offline.split(CUTOFF_MARKER)[0]
    files = {"Guest-Prelogin.txt": prelogin, "GUEST-OFFLINE.txt": offline,
             "GUEST-STAGE.txt": prefix + stage_tail,
             "GUEST-STARTUP.txt": prefix + startup_tail,
             "GUEST-SESSION.txt": guest_session(prelogin, offline, stage_tail, startup_tail, pin),
             "START-HERE.txt": START_HERE}
    encoded = {name: text.encode("utf-8") for name, text in files.items()}
    hashes = {name: sha256(raw) for name, raw in encoded.items()}
    cache_files = sorted(manifest["files"], key=lambda item: item["path"])
    replacements = {"__CACHE_RUN__": cache_run, "__CACHE_MANIFEST_SHA256__": manifest_sha256,
                    "__CACHE_FILES_JSON__": canonical_json(cache_files).replace("'", "''"),
                    "__PACKAGE_FILES_JSON__": canonical_json(hashes).replace("'", "''")}
    for key, name in (("SESSION", "GUEST-SESSION.txt"), ("PRELOGIN", "Guest-Prelogin.txt"),
                      ("OFFLINE", "GUEST-OFFLINE.txt"), ("STAGE", "GUEST-STAGE.txt"),
                      ("STARTUP", "GUEST-STARTUP.txt")):
        replacements["__" + key + "_SOURCE_SHA256__"] = hashes[name]
    host = (source_dir / "HOST-RESTART.template.txt").read_text(encoding="utf-8")
    for key, value in replacements.items():
        if key not in host:
            raise ValueError("host template is missing " + key)
        host = host.replace(key, value)
    if re.search(r"__[A-Z][A-Z0-9_]*__", host):
        raise ValueError("unresolved host template placeholder")
    encoded["HOST-RESTART.txt"] = host.encode("utf-8")
    metadata = {"schema": 1, "package": "MGSV-QA-restart", "cache_run": cache_run,
                "cache_manifest_sha256": manifest_sha256, "cache_files": cache_files,
                "package_files": hashes, "host_sha256": sha256(encoded["HOST-RESTART.txt"]),
                "executed_source_attested": False, "gameplay_verified": False,
                "save_isolation_verified": False, "offline_license_verified": False,
                "co_op_verified": False}
    encoded["package-manifest.json"] = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in encoded.items():
        (output / name).write_bytes(raw)
    archive_path = output / "MGSV-QA-restart.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(encoded.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return archive_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cache-run", required=True)
    parser.add_argument("--manifest-sha256", required=True,
                        help="SHA256 of the previously verified private cache manifest")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(generate(args.output, args.manifest, args.cache_run, args.manifest_sha256))


if __name__ == "__main__":
    main()
