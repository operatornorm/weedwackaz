"""Generate an opt-in, guest-only Steam preparation profile; never start it here."""
import argparse
import base64
import json
from pathlib import Path
import re
import textwrap
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PIN=ROOT/'qa/steam-installer-pin.json'


def load_pin(path=PIN):
    value=json.loads(Path(path).read_text())
    if (value.get('schema')!=1 or value.get('package_identifier')!='Valve.Steam'
        or value.get('installer_url')!='https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe'
        or not isinstance(value.get('installer_sha256'),str)
        or not re.fullmatch('[0-9a-f]{64}',value['installer_sha256']) or value['installer_sha256']=='0'*64
        or not re.fullmatch('[0-9a-f]{40}',value.get('manifest_commit',''))):
        raise ValueError('Steam installer pin is incomplete or not the approved official endpoint')
    return value


def guest_install_commands(pin):
    # Text for the owner to read and paste into an INTERACTIVE guest PowerShell.
    # It is never evaluated by the profile's logon command. Normal signature/TLS,
    # browser attachment checks and installer dialogs remain in place.
    body='''$ErrorActionPreference = 'Stop'
$mgsvGuestIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($mgsvGuestIdentity -notmatch '\\\\WDAGUtilityAccount$') {
    throw 'Use Windows PowerShell INSIDE the Windows Sandbox window only.'
}
$mgsvSteamInstaller = Join-Path $env:USERPROFILE 'Downloads\\SteamSetup.exe'
$mgsvSteamExpectedHash = 'SHA256_PIN'
$mgsvSteamActualHash = (Get-FileHash -LiteralPath $mgsvSteamInstaller -Algorithm SHA256).Hash
if ($mgsvSteamActualHash -ne $mgsvSteamExpectedHash) {
    throw 'Steam installer hash mismatch. Stop and report this message; do not run the installer.'
}
$mgsvSteamSignature = Get-AuthenticodeSignature -LiteralPath $mgsvSteamInstaller
if ($mgsvSteamSignature.Status.ToString() -ne 'Valid') {
    throw 'Steam installer signature is not valid. Stop and report this message.'
}
Start-Process -FilePath $mgsvSteamInstaller -Wait
'''.replace('SHA256_PIN',pin['installer_sha256'])
    # Interactive multiline paste may otherwise execute later statements after
    # a top-level throw. One invocation keeps every guard and launch together.
    return '& {\n'+textwrap.indent(body,'    ')+'}\n'


def instructions(pin):
    return '''Steam preparation inside this Windows Sandbox only

This window belongs to a disposable Windows guest. There are NO mapped host
folders and host clipboard/printer/microphone/camera sharing is disabled.
Networking is ENABLED for the official Steam download and client self-updates.
Closing Sandbox discards all of its contents. No game files are provided.

1. The guest browser opens the official SteamSetup.exe download. Save it as
   SteamSetup.exe in this guest's Downloads folder. Do not open/run it yet.
   Browser first-run setup does not require a Microsoft account; skip sign-in.
2. In this guest, open Start, search Windows PowerShell and open it normally.
3. Read and select ONLY the commands between BEGIN and END below, copy them
   using Ctrl+C, then paste into that GUEST PowerShell with Ctrl+V and Enter.
   Copying within the guest works; host clipboard sharing stays disabled.
4. The commands check the exact pinned SHA256 and Windows Authenticode trust,
   then open the official interactive Steam installer. Keep its standard
   C:\\Program Files (x86)\\Steam destination inside the guest. Complete its normal
   dialogs and any guest-only administrator prompt. There is no silent install
   or automatic license acceptance.
5. Let Steam install/update. STOP at the Steam sign-in screen: do not log in or
   install/launch a game in this stage. Report whether that screen appeared,
   or the exact preparation error. Do not send screenshots or Steam logs.

BEGIN COMMANDS

'''+guest_install_commands(pin)+'''
END COMMANDS

The pin applies to the small Steam bootstrapper only. Steam's own later updates
can download hundreds of MB or more and use Valve's normal update verification;
they are not covered by this bootstrapper SHA. A hash mismatch is a stop, never
permission to learn a new hash or bypass signature checks.

No credentials are needed for this stage. Same-session offline control and game
staging still need a separate verified procedure before login or game access.
This is not save isolation or MGSV/co-op validation. You can keep this anonymous
guest open while continuing immediately; closing it discards the Steam setup.
'''


def logon_script(text,pin):
    data=base64.b64encode(text.encode('utf-8')).decode('ascii')
    # Base64 carries readable UTF8 instructions as DATA, not an evaluated script.
    # The only startup actions are an exclusive guest-local text write and
    # opening Notepad/browser. Fixed program paths avoid PATH/file associations.
    return '''$ErrorActionPreference = 'Stop'
$mgsvGuestIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($mgsvGuestIdentity -notmatch '\\\\WDAGUtilityAccount$') { throw 'Unexpected guest context.' }
$mgsvInstructionsPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'MGSV-Steam-preparation.txt'
$mgsvInstructionsBytes = [Convert]::FromBase64String('INSTRUCTION_DATA')
$mgsvInstructionsFile = [IO.File]::Open($mgsvInstructionsPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $mgsvInstructionsFile.Write($mgsvInstructionsBytes, 0, $mgsvInstructionsBytes.Length) } finally { $mgsvInstructionsFile.Dispose() }
Start-Process -FilePath (Join-Path $env:WINDIR 'System32\\notepad.exe') -ArgumentList ('"' + $mgsvInstructionsPath + '"')
Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList 'STEAM_URL'
'''.replace('INSTRUCTION_DATA',data).replace('STEAM_URL',pin['installer_url'])


def profile(script):
    root=ET.Element('Configuration')
    for key,value in (
        ('VGpu','Enable'),('Networking','Enable'),('AudioInput','Disable'),('VideoInput','Disable'),
        ('PrinterRedirection','Disable'),('ClipboardRedirection','Disable'),('MemoryInMB','4096')):
        ET.SubElement(root,key).text=value
    command=ET.SubElement(ET.SubElement(root,'LogonCommand'),'Command')
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    command.text='C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoLogo -NoProfile -EncodedCommand '+encoded
    # No MappedFolders at all. Unlike the earlier probe there is no writable
    # host Output, so choosing an installer directory cannot select a host map.
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def generate(destination,pin_path=PIN):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    pin=load_pin(pin_path)
    text=instructions(pin);script=logon_script(text,pin)
    (destination/'Steam-preparation.wsb').write_bytes(profile(script))
    (destination/'GUEST-INSTRUCTIONS.txt').write_text(text,encoding='utf-8')
    (destination/'LOGON-SOURCE.ps1').write_text(script,encoding='utf-8')
    (destination/'steam-installer-pin.json').write_text(json.dumps(pin,indent=2)+'\n')
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(generate(args.output))


if __name__=='__main__':main()
