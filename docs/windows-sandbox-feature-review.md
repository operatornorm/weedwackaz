# Proposed Windows Sandbox feature change

Status: owner explicitly approved installing Windows Sandbox on the test PC.
The subsequent owner-run checker now reports functional launch and all expected
harness observations PASS. No command below was run by the cloud. The first
prerequisite attempt returned BLOCKED/sandbox_feature_unavailable
before RAM, graphics or guest tests. That means it could not find the system
launcher; the actual optional-feature state has not yet been queried.

Target: Windows 10 Pro 22H2. Proposed change: query the Windows Sandbox component,
then enable it and required parent components only if Windows reports it disabled.
This is a host Windows feature change. It needs administrator access, may download
Windows component files and may require a reboot. The command explicitly prevents
an automatic restart. It does not install Steam, sign into accounts, launch MGSV,
or change any game files/saves.

## Approved graphical installation route

1. Save current work. Press Windows+R, enter optionalfeatures, and press Enter.
2. In Turn Windows features on or off, find Windows Sandbox.
3. If unchecked, check it and click OK; accept the required Windows components.
   If already checked, leave it unchanged and report that state for diagnosis.
4. Let Windows finish applying/downloading its components, then restart when ready.
5. Extract the existing checker ZIP into a new folder and run ww-sandbox-check.exe
   normally. Return ww-sandbox-result.json. Existing reports cannot be overwritten.

## Exact commands for review

The owner may use the built-in **Windows PowerShell**, opened with **Run as
administrator**. The following first queries the feature and stops on errors.
Enabled, pending or unexpected states cause no enablement attempt.

```powershell
$ErrorActionPreference = 'Stop'
$mgsvSandboxFeatureName = 'Containers-DisposableClientVM'
$mgsvSandboxFeature = Get-WindowsOptionalFeature -Online -FeatureName $mgsvSandboxFeatureName
$mgsvSandboxFeature | Select-Object FeatureName, State

if ($mgsvSandboxFeature.State.ToString() -in @('Disabled', 'DisabledWithPayloadRemoved')) {
    $mgsvSandboxChange = Enable-WindowsOptionalFeature -Online -FeatureName $mgsvSandboxFeatureName -All -NoRestart
    $mgsvSandboxChange | Select-Object Online, RestartNeeded
    Get-WindowsOptionalFeature -Online -FeatureName $mgsvSandboxFeatureName |
        Select-Object FeatureName, State
} else {
    Write-Output 'No feature change made. Report the displayed state before continuing.'
}
```

`-All` enables the parent components required by this feature; it does not enable
all Windows features. If Windows reports an error or the feature is already
enabled while its launcher is missing, stop for diagnosis. No automatic component
repair, firmware, boot configuration or security-setting change is proposed.

After a successful change, finish other work before a normal user-initiated reboot
if Windows requires one. Then rerun the existing helper from a fresh extraction
and return its JSON. The tool still performs no Steam/game/account actions.

## Reversal and limits

For reference, the Windows command to disable Sandbox is:

```powershell
Disable-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM' -NoRestart
```

This may also require a reboot. It does not automatically remove shared parent
components enabled by `-All`; do not remove shared components blindly. Enabling
the feature does not establish that virtualization, guest boot or hardware D3D11
will work. The existing automated probe remains the next verification gate.

The permission requirement comes from
[Coop Anything AGENTS.md](https://github.com/cranebeaker/coop-anything/blob/main/AGENTS.md#ground-rules):
“Ask your owner before … installing software.” Prior permission for cloud build
tools or the standalone Steam checker did not cover a host Windows feature change.
