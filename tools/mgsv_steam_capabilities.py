#!/usr/bin/env python3
"""Read-only Steam DLL metadata probe. Does not load DLLs, launch Steam or touch saves."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import struct

EXE_SHA256="f3818d172293800171a344a71957bc7257f591bbf7c1792e10fef6bfbba7f4f2"
INTERFACES=re.compile(rb"(?<![A-Za-z0-9_])(?:SteamClient|SteamFriends|SteamMatchMaking|SteamMatchMakingServers|SteamUser|STEAMFRIENDS_INTERFACE_VERSION|SteamUtils|STEAMAPPS_INTERFACE_VERSION)[0-9]{3}(?![A-Za-z0-9_])")


class Invalid(ValueError): pass


def exports(data):
    def need(offset,size):
        if offset < 0 or size < 0 or offset+size > len(data): raise Invalid("pe_span_out_of_bounds")
        return offset
    def u16(offset): return struct.unpack_from("<H",data,need(offset,2))[0]
    def u32(offset): return struct.unpack_from("<I",data,need(offset,4))[0]
    if len(data)<64 or data[:2]!=b"MZ": raise Invalid("not_pe")
    pe=u32(0x3c);need(pe,24)
    if data[pe:pe+4]!=b"PE\0\0" or u16(pe+4)!=0x8664: raise Invalid("not_windows_amd64")
    count,optional_size=u16(pe+6),u16(pe+20)
    optional=pe+24;need(optional,optional_size)
    if not 1 <= count <= 96 or optional_size < 120 or u16(optional)!=0x20b or u32(optional+108)<1: raise Invalid("invalid_pe_headers")
    sections=optional+optional_size;need(sections,count*40)
    mappings=[]
    for i in range(count):
        row=sections+i*40
        virtual,raw_size,raw=u32(row+12),u32(row+16),u32(row+20)
        need(raw,raw_size);mappings.append((virtual,raw_size,raw))
    def rva(address,size):
        candidates=[raw+address-base for base,length,raw in mappings if address>=base and address-base+size<=length]
        if len(candidates)!=1: raise Invalid("ambiguous_or_unmapped_rva")
        return need(candidates[0],size)
    directory,size=u32(optional+112),u32(optional+116)
    if not directory or size<40: raise Invalid("missing_export_directory")
    start=rva(directory,40);names=u32(start+24)
    if names>16384: raise Invalid("too_many_exports")
    table=rva(u32(start+32),names*4)
    selected=[]
    for i in range(names):
        address=u32(table+i*4);offset=rva(address,1)
        end=data.find(b"\0",offset,min(offset+129,len(data)))
        if end<0: raise Invalid("invalid_export_name")
        # Ensure the entire string is backed by the same unambiguous section.
        rva(address,end-offset+1)
        name=data[offset:end].decode("ascii",errors="strict")
        if (name.startswith("Steam") or name=="CreateInterface") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_@]{0,127}",name): selected.append(name)
    versions=sorted({v.decode("ascii") for v in INTERFACES.findall(data)})
    if len(versions)>256: raise Invalid("interface_candidate_limit")
    return {"machine":"amd64","named_export_count":names,"steam_exports":sorted(set(selected)),"interface_string_candidates":versions}


def sha256(path):
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 536870912: raise Invalid("executable_size_or_type_limit")
    digest=hashlib.sha256()
    total=0
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1048576),b""):
            total+=len(chunk)
            if total>536870912: raise Invalid("executable_size_limit")
            digest.update(chunk)
    return digest.hexdigest()


def interface_candidates(path):
    # Interface version literals are often in the game, not the Steam DLL.
    found=set();carry=b"";total=0
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1048576),b""):
            total+=len(chunk)
            if total>536870912: raise Invalid("executable_size_limit")
            text=carry+chunk
            base=total-len(text)
            # Defer a match touching the chunk end until its following byte is
            # known. Ignore an overlap-start match whose preceding byte was lost.
            found.update(m.group().decode("ascii") for m in INTERFACES.finditer(text)
                         if m.end()<len(text) and (m.start()>0 or base==0))
            if len(found)>256: raise Invalid("interface_candidate_limit")
            carry=text[-256:]
    base=total-len(carry)
    found.update(m.group().decode("ascii") for m in INTERFACES.finditer(carry) if m.start()>0 or base==0)
    if len(found)>256: raise Invalid("interface_candidate_limit")
    return sorted(found)


def report(game):
    exe=game/"mgsvtpp.exe";dll=game/"steam_api64.dll"
    if exe.is_symlink() or dll.is_symlink(): raise Invalid("symlink_input")
    before=exe.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 536870912: raise Invalid("executable_size_or_type_limit")
    identity=sha256(exe)
    if identity!=EXE_SHA256: raise Invalid("executable_fingerprint_mismatch")
    info=dll.stat()
    if not stat.S_ISREG(info.st_mode): raise Invalid("steam_dll_not_regular")
    size=info.st_size
    if not 512 <= size <= 33554432: raise Invalid("steam_dll_size_limit")
    with dll.open("rb") as stream: content=stream.read(33554433)
    if len(content)!=size: raise Invalid("steam_dll_changed_while_reading")
    metadata=exports(content)
    executable_interfaces=interface_candidates(exe)
    after=exe.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise Invalid("executable_changed_while_reading")
    return {"schema":1,"kind":"mgsv_steam_capabilities","read_only":True,"can_install":False,
            "executable_sha256":identity,"executable_interface_string_candidates":executable_interfaces,
            "steam_api64":{"sha256":hashlib.sha256(content).hexdigest(),"size":size,**metadata},
            "runtime_interfaces_verified":False,"invite_callbacks_verified":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    game=args.game_dir.resolve()
    if args.output.resolve().is_relative_to(game): parser.error("output must be outside the game folder")
    try: value=report(game)
    except (OSError,Invalid,UnicodeError):
        print("BLOCKED: expected pinned executable and readable regular 64-bit Steam API DLL; no files changed")
        return 2
    try:
        with args.output.open("x",encoding="utf-8") as stream: json.dump(value,stream,indent=2);stream.write("\n")
    except OSError:
        print("BLOCKED: output already exists or cannot be written; choose a new output filename")
        return 2
    print("Steam DLL metadata report written. No DLLs loaded, no game launched, no saves accessed.")
    return 0


if __name__=="__main__": raise SystemExit(main())
