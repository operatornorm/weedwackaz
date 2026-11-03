#!/usr/bin/env python3
"""Package our single stdlib-only read-only probe, without any game/SDK files."""
from pathlib import Path
import hashlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'build-artifacts/steam-capabilities'
target.mkdir(parents=True,exist_ok=True)
output=target/'mgsv-steam-capabilities.pyz'
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    entry=zipfile.ZipInfo('__main__.py',(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
    entry.external_attr=0o100644<<16
    archive.writestr(entry,(ROOT/'tools/mgsv_steam_capabilities.py').read_bytes())
digest=hashlib.sha256(output.read_bytes()).hexdigest()
(target/'SHA256SUMS').write_text(digest+'  '+output.name+'\n')
print(output.name,output.stat().st_size,digest)
