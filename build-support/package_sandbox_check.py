#!/usr/bin/env python3
"""Package the standalone offline Sandbox prerequisite helper and own sources."""
from pathlib import Path
import hashlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-artifacts/windows-sandbox-check'
README='''MGSV isolated-test prerequisite: Windows Sandbox harness check

This tool does not start Steam/MGSV, use accounts, install software, enable Windows
features, change firmware/security settings, or copy game files/saves. It uses an
ALREADY installed Windows Sandbox. If unavailable it reports BLOCKED and stops.
The candidate configuration is intended for Windows 10 Pro 22H2; actual guest
boot/mapping/graphics behavior is not yet tested. No administrator run is needed.

1. Extract the complete ZIP to a NEW writable folder outside Steam/game folders,
   for example a new folder under Downloads. Keep the helper there.
2. Double-click ww-sandbox-check.exe. It first checks for the system Sandbox
   launcher, an existing Sandbox session, and memory for this harness (at least
   8 GiB installed and 5 GiB available). It never takes over or kills a session.
3. If preflight permits, it starts Windows Sandbox and runs its probe automatically.
   Wait for the completion message, up to three minutes. No manual guest input is
   needed. The Sandbox window can remain open after the probe.
4. Send ww-sandbox-result.json from the extracted helper folder, including
   BLOCKED/FAIL/TIMEOUT results. Existing reports are never overwritten; use a
   fresh extraction for a requested rerun. If Sandbox was opened for this check,
   you may close that window once the probe finishes.

If unavailable or blocked, return the report/message. Do not enable/install
features, run as administrator or change security settings for this check.

The helper creates a new ww-sandbox-run-<nonce> directory beside itself. Only its
own hash-checked executable is staged into Input, which is mapped READ ONLY.
Only that run's new Output folder is mapped read/write. The parent Downloads
folder, Steam, account profiles and game folders are not mapped. The WSB file
requests networking off, vGPU on, 4 GiB RAM, clipboard/printer redirection off and
microphone/camera input redirection off. There is no Steam software or login.

The automatic guest probe checks guarded guest/path observations, denial of a
new input write, its own empty output/scratch write/delete probes, local adapter
observations (no Internet request) and hardware D3D11 feature 11_0. A software
adapter cannot pass. It does not capture a desktop, list files or export adapter
names/addresses, computer/user paths, process lists or account identifiers.

The guest's bounded 72-byte packet must match this run's nonce and helper hash.
The host writes fixed status/boolean JSON plus the nonce, OUR binary hash and a
D3D result code. Launcher success, missing/partial/stale reports or absent checks
cannot PASS. The generated WSB contains local folder paths: send only the result
JSON, not the WSB or the run folder.

PASS covers only these harness observations. It is not VM attestation, proof of
all host-drive/network isolation, Steam/MGSV compatibility, runtime save isolation
or playable co-op. Those report fields remain false. A separate Steam/Cloud/save
procedure must be prepared and approved before any later instrumented game run.

Source is included under source/. Microsoft/Valve binaries or SDK headers are
not included. Rebuild with an EXISTING MinGW C++23 toolchain:
x86_64-w64-mingw32-g++ -std=c++23 -O2 -s -static -Wall -Wextra -Werror -Wno-cast-function-type -municode -mwindows -I source/tools/windows-sandbox-check source/tools/windows-sandbox-check/main.cpp -lbcrypt -ld3d11 -ldxgi -ldxguid -luuid -liphlpapi -lws2_32 -ladvapi32 -lshell32 -o ww-sandbox-check.exe
Portable plan/report tests with an EXISTING Python3 and host C++23 compiler:
python3 -m unittest discover -s source/tests -p test_sandbox_plan.py -v

Platform references (live pages are blocked by the cloud's HTTP policy, so exact
candidate settings remain subject to the automated guest result):
https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-overview
https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file
'''


def main():
    files={'README.txt':README.encode(),'ww-sandbox-check.exe':(OUT/'ww-sandbox-check.exe').read_bytes(),
        'LICENSE.txt':(ROOT/'patches/DYNAMITE-LICENSE').read_bytes()}
    for path in ('tools/windows-sandbox-check/Plan.h','tools/windows-sandbox-check/main.cpp',
        'tests/sandbox_plan.cpp','tests/test_sandbox_plan.py','build-support/build-sandbox-check-offline.sh'):
        files['source/'+path]=(ROOT/path).read_bytes()
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(value).hexdigest()+'  '+name+'\n' for name,value in sorted(files.items())).encode()
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'ww-sandbox-check.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,value in sorted(files.items()):
            item=zipfile.ZipInfo(name,(1980,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16
            archive.writestr(item,value)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT/'SHA256SUMS-zip.txt').write_text(digest+'  '+target.name+'\n')
    print(target.name,target.stat().st_size,digest)


if __name__=='__main__':main()
