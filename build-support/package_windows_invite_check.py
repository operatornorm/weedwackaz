#!/usr/bin/env python3
"""Package only our synthetic Windows binding test, sources and license."""
from pathlib import Path
import hashlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build-artifacts/experimental-steam-invites/windows-fixture'
OUT=ROOT/'build-artifacts/windows-invite-check'
OUT.mkdir(parents=True,exist_ok=True)
source=ROOT.parent/'dynamite/hook/src'
readme='''Synthetic Windows invite-binding check

This check loads only the supplied ww-invite-fake.dll. It does not start Steam or
MGSV, read accounts/saves, install software or contact the network. Run it under
your usual Windows login. It is not a co-op mod installer or a real Steam test.

Extract the ZIP into a NEW empty folder outside the game/Steam folders. Keep both
binary files together. Double-click ww-invite-abi-check.exe. It creates
ww-invite-abi-result.json next to itself; send only that JSON back to the chat.
Existing reports are never overwritten; extract to a fresh folder for a rerun.

If Windows blocks execution or no report appears, report the message. Do not
disable security software or install/copy the DLL into a game directory.

PASS covers Windows loading/function lookup and callback flow between OUR two
test modules. It does not validate the real Valve DLL, Steam accounts, game invite
routing, save isolation or multiplayer. Those remain later test gates.

Source is included under source/. The declarations derive ABI facts from Valve's
official Proton commit e91ca2be0df2cef4c230cbbc0b86604d73a0bbf6, SDK135. No Valve SDK
source or redistributable DLL is included. Fixture IDs and invitations are synthetic.
'''
files={
    'README.txt':readme.encode(),
    'ww-invite-abi-check.exe':(BUILD/'ww-invite-abi-check.exe').read_bytes(),
    'ww-invite-fake.dll':(BUILD/'ww-invite-fake.dll').read_bytes(),
    'LICENSE.txt':(ROOT/'patches/DYNAMITE-LICENSE').read_bytes(),
}
for name in ('SteamInviteProtocol.h','SteamInviteBindings.h'):
    files['source/'+name]=(source/name).read_bytes()
for name in ('steam_invite_fake_api.h','steam_invite_fake_dll.cpp','steam_invite_windows_check.cpp'):
    files['source/'+name]=(ROOT/'tests'/name).read_bytes()
files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
target=OUT/'ww-invite-windows-check.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name,data in sorted(files.items()):
        entry=zipfile.ZipInfo(name,(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16
        archive.writestr(entry,data)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(OUT/'SHA256SUMS').write_text(digest+'  '+target.name+'\n')
print(target.name,target.stat().st_size,digest)
