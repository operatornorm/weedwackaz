#!/usr/bin/env python3
"""Package our standalone Steam-context checker without a Valve binary or SDK."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build-artifacts/windows-steam-runtime-check'
EXE = ROOT / 'build-artifacts/experimental-invite-controller/ww-steam-runtime-check.exe'
SOURCE = ROOT.parent / 'dynamite/hook/src'
README = '''MGSV Steam runtime check — approval required before running

This is a standalone development check, not a game installer. It binds to your
SIGNED-IN STEAM ACCOUNT for App 287700 using your existing pinned Steam DLL.
Steam may briefly display you as in MGSV and do normal SDK/client bookkeeping.
It registers then unregisters a callback without pumping callbacks or sending
invitations. It does not launch MGSV, enumerate friends, read/write game saves,
install anything, or change Steam/Cloud settings. It is not a game invitation
delivery, MGO routing, save-isolation, or multiplayer test.

Wait for the owner's explicit approval for this Steam-connected check before
running it. The Coop Anything AGENTS.md requires permission before account use:
https://github.com/cranebeaker/coop-anything/blob/main/AGENTS.md

After approval:
1. Use your normal Windows login. Keep Steam open and signed into the account
   that owns MGSV. Close MGSV first. Administrator access is not needed.
2. Extract the complete ZIP to a NEW writable folder outside Steam/game folders,
   for example a new folder under Downloads. Do not put DLLs into this folder.
   Keep the supplied steam_appid.txt unchanged; it belongs ONLY to this helper.
3. Double-click ww-steam-runtime-check.exe. The file picker asks for the original
   steam_api64.dll in your MGSV 1.0.15.3 CO-OP COPY. Select that existing file;
   do not move, replace or edit it. The helper reads, hashes and loads it in its
   own process only if its exact known fingerprint matches.
4. Send ww-steam-runtime-result.json from the helper folder. The report contains
   fixed status/boolean fields, no account IDs/names or computer paths. Existing
   reports are never overwritten; use a fresh extraction for an approved rerun.

If Windows blocks execution, report the message; do not disable protection.
FAIL is useful too. This helper cannot fix Steam setup or install the mod.

Expected DLL SHA256:
08bd0152356e5619ee56a6714ac951b6800dbb21821693a4efaf85278442c60a
Expected DLL size: 211368 bytes. No Valve DLL or SDK headers are supplied.

The code verifies before executing the selected DLL and holds its source file
against replacement during the check. Callback storage and the loaded module
remain alive until process exit even if cleanup fails. Init/Shutdown belong only
to this standalone process. Game injection must instead borrow the existing
game context; this helper is not an implementation of that game integration.

Own sources/license are included under source/ and LICENSE.txt. ABI references:
ValveSoftware/Proton e91ca2be0df2cef4c230cbbc0b86604d73a0bbf6,
lsteamclient/steamworks_sdk_135/steam_api.h and steam_api_flat.h.

Rebuild with an existing MinGW C++23 toolchain (not an installation instruction):
x86_64-w64-mingw32-g++ -std=c++23 -O2 -s -static -Wall -Wextra -Werror -Wno-cast-function-type -municode -mwindows -I source source/main.cpp -lbcrypt -lcomdlg32 -o ww-steam-runtime-check.exe
The included fake-API fixture can be compiled with an existing host C++23 compiler:
g++ -std=c++23 -pthread -I source source/dynamite_steam_runtime_check.cpp -o runtime-fixture
Only the portable pipeline has been executed in cloud; Windows loader/Steam runtime
execution remains pending owner approval. Do not substitute a fake DLL in this check.
'''


def main():
    files = {
        'README.txt': README.encode(),
        'ww-steam-runtime-check.exe': EXE.read_bytes(),
        'steam_appid.txt': b'287700\n',
        'LICENSE.txt': (ROOT / 'patches/DYNAMITE-LICENSE').read_bytes(),
    }
    for name in ('RuntimeCheck.h', 'main.cpp'):
        files['source/' + name] = (ROOT / 'tools/steam-runtime-check' / name).read_bytes()
    for name in ('SteamInviteProtocol.h', 'SteamInviteBindings.h'):
        files['source/' + name] = (SOURCE / name).read_bytes()
    files['source/dynamite_steam_runtime_check.cpp'] = (ROOT / 'tests/dynamite_steam_runtime_check.cpp').read_bytes()
    files['source/steam_invite_fake_api.h'] = (ROOT / 'tests/steam_invite_fake_api.h').read_bytes()
    files['SHA256SUMS.txt'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in sorted(files.items())).encode()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'ww-steam-runtime-check.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / 'SHA256SUMS').write_text(digest + '  ' + target.name + '\n')
    print(target.name, target.stat().st_size, digest)


if __name__ == '__main__':
    main()
