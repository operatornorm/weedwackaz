#!/usr/bin/env python3
"""Read-only MGSV package metadata reporter; Python standard library only.

Copy this entire TEXT file into a local editor; no binary download is needed.
Uses the same pinned format facts as tools/mgsv-pack-report. No game execution,
installation, asset extraction, Steam userdata access, or save/configuration writes.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import struct
import sys
import zlib

MASK = (1 << 64) - 1
K0, K1, K2, K3 = (0xc3a5c85c97cb3127, 0xb492b66fbe98f273,
                   0x9ae16a3b2f90404f, 0xc949d7c7509e6557)
XOR = (0x41441043, 0x11c22050, 0xd05608c3, 0x532c7319)
KEYS = (0xbb8adedb, 0x65229958, 0x08453206, 0x88121302,
        0x4c344955, 0x2c02f10c, 0x4887f823, 0xf3818583)
MAX_PACK = 64 << 20
MAX_TOTAL = 256 << 20
MAX_RECORDS = 25000


class ReportError(ValueError):
    """A fixed diagnostic code, safe to include without local paths or payloads."""


def require(condition, code):
    if not condition:
        raise ReportError(code)


def failure_code(error):
    if isinstance(error, ReportError):
        return str(error)
    if isinstance(error, zlib.error):
        return "container_zlib_invalid"
    if isinstance(error, OSError):
        return "io_read_failed"
    return "binary_structure_failed"


def u64(value):
    return value & MASK


def rotate(value, bits):
    value &= MASK
    return ((value >> bits) | (value << (64 - bits))) & MASK if bits else value


def mix(value):
    value &= MASK
    return value ^ (value >> 47)


def hash16(a, b):
    multiplier = 0x9ddfea08eb382d69
    a = u64((u64(a) ^ u64(b)) * multiplier)
    a ^= a >> 47
    b = u64((u64(b) ^ a) * multiplier)
    b ^= b >> 47
    return u64(b * multiplier)


def get64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def get32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def weak(data, a, b):
    w, x, y, z = struct.unpack_from("<4Q", data)
    a = u64(a + w)
    b = rotate(b + a + z, 21)
    c = a
    a = u64(a + x + y)
    b = u64(b + rotate(a, 44))
    return u64(a + z), u64(b + c)


def city64(data):
    # This bounded variant matches the pinned hashing implementation on 0..128 bytes.
    n = len(data)
    require(n <= 128, "hash_name_length_limit")
    if n <= 16:
        if n > 8:
            a, b = get64(data, 0), get64(data, n - 8)
            return hash16(a, rotate(b + n, n)) ^ b
        if n >= 4:
            return hash16(n + (get32(data, 0) << 3), get32(data, n - 4))
        if n:
            y, z = data[0] + (data[n >> 1] << 8), n + (data[n - 1] << 2)
            return u64(mix(u64(y * K2) ^ u64(z * K3)) * K2)
        return K2
    if n <= 32:
        a, b = u64(get64(data, 0) * K1), get64(data, 8)
        c, d = u64(get64(data, n - 8) * K2), u64(get64(data, n - 16) * K0)
        return hash16(rotate(a - b, 43) + rotate(c, 30) + d,
                      a + rotate(b ^ K3, 20) - c + n)
    if n <= 64:
        z = get64(data, 24)
        a = u64(get64(data, 0) + (n + get64(data, n - 16)) * K0)
        b, c = rotate(a + z, 52), rotate(a, 37)
        a = u64(a + get64(data, 8))
        c = u64(c + rotate(a, 7))
        a = u64(a + get64(data, 16))
        vf, vs = u64(a + z), u64(b + rotate(a, 31) + c)
        a = u64(get64(data, 16) + get64(data, n - 32))
        z = get64(data, n - 8)
        b, c = rotate(a + z, 52), rotate(a, 37)
        a = u64(a + get64(data, n - 24))
        c = u64(c + rotate(a, 7))
        a = u64(a + get64(data, n - 16))
        wf, ws = u64(a + z), u64(b + rotate(a, 31) + c)
        return u64(mix(mix((vf + ws) * K2 + (wf + vs) * K0) * K0 + vs) * K2)
    x = get64(data, n - 40)
    y = u64(get64(data, n - 16) + get64(data, n - 56))
    z = hash16(get64(data, n - 48) + n, get64(data, n - 24))
    v, w = weak(data[n - 64:], n, z), weak(data[n - 32:], y + K1, x)
    x = u64(x * K1 + get64(data, 0))
    x = u64(rotate(x + y + v[0] + get64(data, 8), 37) * K1)
    y = u64(rotate(y + v[1] + get64(data, 48), 42) * K1)
    x ^= w[1]
    y = u64(y + v[0] + get64(data, 40))
    z = u64(rotate(z + w[0], 33) * K1)
    v = weak(data, v[1] * K1, x + w[0])
    w = weak(data[32:], z + w[1], y + get64(data, 16))
    z, x = x, z
    return hash16(hash16(v[0], w[0]) + mix(y) * K1 + z,
                  hash16(v[1], w[1]) + x)


def path_hash(name):
    extension = {"fpk": 0xa45, "fpkd": 0x1daa}[name.rsplit(".", 1)[1]]
    require(name.startswith("/Assets/"), "unexpected_probe_namespace")
    data = name[8:].rsplit(".", 1)[0].encode("ascii")
    seed = int.from_bytes(data[-8:], "big")
    return (extension << 51) | (hash16(city64(data) - K2, seed) & 0x3ffffffffffff)


def seeds():
    names = ["f30010/f30010", "f30010/f30011", "f30020/f30020",
             "f30050/f30050", "f30050/f30051", "f30050/f30050_Buddy",
             "f30150/f30150", "f30250/f30250"]
    names += ["f30050/f30050_hanger_btg%02d" % n for n in range(100)]
    result = ["/Assets/tpp/pack/mission2/free/" + name + suffix
              for name in names for suffix in (".fpk", ".fpkd")]
    result += ["/Assets/tpp/pack/mission2/common/mis_com_" + name + suffix
               for name in ("afgh", "mafr", "mtbs") for suffix in (".fpk", ".fpkd")]
    return result


def read_at(file, offset, length, total):
    require(0 <= offset <= total and 0 <= length <= total - offset, "archive_bounds")
    file.seek(offset)
    data = file.read(length)
    require(len(data) == length, "archive_truncated")
    return data


def index_archive(file, size):
    header = read_at(file, 0, 32, size)
    require(header[:4] == b"SQAR", "qar_magic")
    count, version = get32(header, 8) ^ XOR[1], get32(header, 24) ^ XOR[0]
    require(version in (1, 2), "qar_version")
    require(count <= 250000, "qar_entry_limit")
    table = read_at(file, 32, count * 8, size)
    shift = 12 if (get32(header, 4) ^ XOR[0]) & 0x800 else 10
    state, result = 0xa2c18ec3, []
    for i in range(count):
        a, b = struct.unpack_from("<II", table, i * 8)
        p = state if version == 2 else i
        a ^= XOR[(p + i * 8 // 5) % 4]
        b ^= XOR[(p + (i * 8 + 4) // 5) % 4]
        if version == 2:
            r = (b // 256) % 19
            state ^= ((a >> r) | (a << (32 - r))) & 0xffffffff
        offset = (((b << 32) | a) >> 40) << shift
        require(offset >= 32 + count * 8, "qar_entry_header_bounds")
        row = read_at(file, offset, 32, size)
        name_hash = get64(row, 0) ^ 0x4144104341441043
        stored, decoded = get32(row, 8) ^ XOR[1], get32(row, 12) ^ XOR[2]
        require(stored <= size - offset - 32, "qar_payload_bounds")
        checksum = struct.pack("<4I", *(get32(row, 16 + j * 4) ^ mask
                                      for j, mask in enumerate((XOR[3], XOR[0], XOR[0], XOR[1]))))
        result.append((name_hash, offset + 32, stored, decoded, checksum, i))
    return version, result


def decode(file, size, version, entry, verification=None):
    name_hash, offset, stored, decoded, checksum, _ = entry
    require(8 <= stored <= MAX_PACK + 16 and decoded <= MAX_PACK + 16, "container_size_limit")
    raw = bytearray(read_at(file, offset, stored, size))
    low = name_hash & 0xffffffff
    seed = int.from_bytes(checksum[(low % 2) * 8:(low % 2 + 1) * 8], "little") if version == 2 else 0
    for position in range(0, len(raw), 8):
        index = 2 * ((low + seed + position // 11) % 4)
        mask = ((KEYS[index + 1] << 32) | KEYS[index]) ^ seed
        for j in range(min(8, len(raw) - position)):
            raw[position + j] ^= (mask >> (8 * j)) & 255
    # datfpk's writer hashes this representation, while GzsTool/stock fixtures
    # hash the decoded payload. Both conventions still require full decoding.
    stored_digest = hashlib.md5(raw).digest()
    magic = get32(raw, 0)
    header = {0xa0f8efe6: 8, 0xe3f8efe6: 16}.get(magic, 0)
    require(len(raw) >= header and decoded >= header, "container_encryption_header")
    expected = decoded - header
    if header:
        if header == 16:
            expected = get32(raw, 8)
            require(decoded in (expected, expected + header) and
                    get32(raw, 12) == stored - header, "container_inner_length")
        key = get32(raw, 4)
        step, state = (key * 278) & 0xffffffff, (key | ((key ^ 25974) << 16)) & 0xffffffff
        raw = raw[header:]
        for position in range(0, len(raw) - 3, 4):
            struct.pack_into("<I", raw, position, get32(raw, position) ^ state)
            state = (step + 48828125 * state) & 0xffffffff
    if stored != decoded:
        inflater = zlib.decompressobj()
        raw = inflater.decompress(raw, MAX_PACK + 1)
        require(inflater.eof, "container_zlib_limit_or_truncation")
        require(not inflater.unused_data and not inflater.unconsumed_tail, "container_zlib_trailing_data")
    require(len(raw) <= MAX_PACK and (len(raw) == expected or
            (header == 8 and len(raw) == decoded)), "container_decoded_length")
    stored_match = stored_digest == checksum
    payload_match = hashlib.md5(raw).digest() == checksum
    require(stored_match or payload_match, "container_checksum_mismatch")
    if verification is not None:
        verification["checksum_stage"] = ("both" if stored_match and payload_match else
                                          "decrypted_stored" if stored_match else "decoded_payload")
    return bytes(raw)


def inspect(data):
    require(48 <= len(data) <= MAX_PACK and data[:10] in (b"foxfpk\x00win", b"foxfpkdwin"), "fpk_header")
    entries, refs = get32(data, 36), get32(data, 40)
    end = 48 + 48 * entries + 16 * refs
    require(get32(data, 32) == 2 and entries + refs <= 4096 and
            end <= len(data) == get32(data, 10), "fpk_table_or_size")

    def name(offset, length):
        require(end <= offset <= len(data) and 0 < length <= 512 and
                length <= len(data) - offset, "fpk_name_bounds")
        raw = data[offset:offset + length]
        text = raw.decode("ascii", "replace")
        if not (re.fullmatch(r"/Assets/[A-Za-z0-9_./-]+", text) and posixpath.normpath(text) == text):
            return "<name omitted>"
        return text

    members = []
    for i in range(entries):
        at = 48 + 48 * i
        offset, length = get32(data, at), get32(data, at + 8)
        require(end <= offset <= len(data) and length <= len(data) - offset, "fpk_member_bounds")
        text = name(get32(data, at + 16), get32(data, at + 24))
        item = {"name": text, "offset": offset, "size": length}
        if text.startswith("/Assets/tpp/level_asset/chara/player/game_object/") and any(
                token in posixpath.basename(text) for token in ("instance", "parts")):
            item["allocation_candidate_by_name"] = True
            item["stored_member_sha256"] = hashlib.sha256(data[offset:offset + length]).hexdigest()
        members.append(item)
    references = [name(get32(data, 48 + 48 * entries + 16 * i),
                       get32(data, 56 + 48 * entries + 16 * i)) for i in range(refs)]
    return {"kind": "fpkd" if data[6:7] == b"d" else "fpk", "members": members,
            "references": references, "container_sha256": hashlib.sha256(data).hexdigest()}


def collect(root):
    result = {"kind": "mgsv_pack_metadata_only_not_gameplay_validation", "version": "python-2",
              "archives": [], "probes": [], "containers": [], "limits_hit": 0,
              "limitations": ["Known archive paths; no load precedence inferred.",
                              "Names/hashes do not establish entity counts or working co-op.",
                              "No keys, member bodies, saves, scripts, account data or PC paths exported.",
                              "64MiB/container, 256MiB decoded, 64 containers, 25000 records, depth2.",
                              "Hash inputs over128bytes are listed but not resolved."]}
    digest = hashlib.sha256()
    with (root / "mgsvtpp.exe").open("rb") as executable:
        count = 0
        for block in iter(lambda: executable.read(1024 * 1024), b""):
            count += len(block)
            require(count <= 512 << 20, "executable_size_limit")
            digest.update(block)
    require(count > 0, "executable_empty")
    result["executable_sha256"] = digest.hexdigest()
    paths = ["master/0/00.dat.vendor", "master/0/00.dat", "master/0/01.dat", "master/data1.dat"]
    paths += ["master/chunk%d.dat" % i for i in range(5)]
    sources, index = [], {}
    try:
        total_entries = 0
        for relative in sorted(paths):
            info = {"archive": relative, "status": "missing_or_unreadable"}
            result["archives"].append(info)
            target = root / relative
            if target.is_symlink() or not target.is_file():
                continue
            file = None
            try:
                file = target.open("rb")
                size = os.fstat(file.fileno()).st_size
                print("Reading archive metadata:", relative, flush=True)
                version, entries = index_archive(file, size)
                total_entries += len(entries)
                require(total_entries <= 1000000, "total_entry_limit")
                source = (file, size, version, relative)
                sources.append(source)
                info.update(status="indexed", entries=len(entries), bytes=size, version=version)
                for entry in entries:
                    index.setdefault(entry[0], []).append((source, entry))
            except (OSError, ValueError, struct.error) as error:
                if file:
                    file.close()
                info["status"] = "archive_parse_or_read_failed"
                info["failure_code"] = failure_code(error)
        pending, queued, seen = [(name, 0) for name in seeds()], set(seeds()), set()
        total_bytes, records = 0, 0

        def enqueue(name, depth):
            if name in queued:
                return
            if len(queued) >= 4096:
                result["limits_hit"] += 1
                return
            queued.add(name)
            pending.append((name, depth))

        def visit(data, node):
            nonlocal records
            if len(result["containers"]) >= 64:
                result["limits_hit"] += 1
                return
            result["containers"].append(node)
            try:
                metadata = inspect(data)
                records += len(metadata["members"]) + len(metadata["references"])
                require(records <= MAX_RECORDS, "metadata_record_limit")
                node.update(status="metadata_ok", metadata=metadata)
                if node["depth"] >= 2:
                    if metadata["references"] or any(m["name"].endswith((".fpk", ".fpkd")) for m in metadata["members"]):
                        result["limits_hit"] += 1
                    return
                for ref in metadata["references"]:
                    if ref.endswith((".fpk", ".fpkd")):
                        enqueue(ref, node["depth"] + 1)
                        if ref.endswith(".fpk"):
                            enqueue(ref + "d", node["depth"] + 1)
                for member in metadata["members"]:
                    if member["name"].endswith((".fpk", ".fpkd")):
                        start = member["offset"]
                        visit(data[start:start + member["size"]], dict(
                            archive=node["archive"], path=member["name"], parent=node["path"], depth=node["depth"] + 1))
            except (ValueError, struct.error) as error:
                node["status"] = "fpk_parse_or_limit_failed"
                node["failure_code"] = failure_code(error)

        print("Inspecting selected package tables...", flush=True)
        cursor = 0
        while cursor < len(pending):
            name, depth = pending[cursor]
            cursor += 1
            try:
                key = path_hash(name)
            except (ValueError, KeyError, UnicodeError):
                result["limits_hit"] += 1
                continue
            matches = index.get(key, [])
            result["probes"].append({"path": name, "matches": len(matches)})
            for source, entry in matches:
                file, size, version, archive = source
                identity = (archive, entry[-1])
                if identity in seen:
                    continue
                seen.add(identity)
                if len(result["containers"]) >= 64 or total_bytes + entry[3] > MAX_TOTAL:
                    result["limits_hit"] += 1
                    continue
                node = {"archive": archive, "path": name, "entry": entry[-1],
                        "hash": "%016x" % key, "depth": depth}
                try:
                    data = decode(file, size, version, entry, node)
                    total_bytes += len(data)
                    visit(data, node)
                except (OSError, ValueError, struct.error, zlib.error) as error:
                    node["status"] = "container_decode_or_limit_failed"
                    node["failure_code"] = failure_code(error)
                    result["containers"].append(node)
        result["containers_inspected"] = sum(node["status"] == "metadata_ok" for node in result["containers"])
        result["containers_failed"] = len(result["containers"]) - result["containers_inspected"]
        result["parse_failures"] = result["containers_failed"] + sum(
            archive["status"] == "archive_parse_or_read_failed" for archive in result["archives"])
        result["enumeration_finished"] = True
        return result
    finally:
        for file, *_ in sources:
            file.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.game_dir.resolve(strict=True)
        parent = args.output.parent.resolve(strict=True)
        require(root != parent and root not in parent.parents, "output_must_be_outside_game_copy")
        result = collect(root)
        data = json.dumps(result, indent=2).encode("utf-8") + b"\n"
        require(len(data) <= 16 << 20, "report_size_limit")
        with (parent / args.output.name).open("xb") as output:
            output.write(data)
    except FileExistsError:
        print("Output already exists; choose a new JSON filename.", file=sys.stderr)
        return 1
    except (OSError, ValueError, struct.error):
        print("Report failed: check the copied-game directory and new output filename.", file=sys.stderr)
        return 1
    print("Metadata report written. Game files were opened read-only.")
    print("Inspected: %d containers; failed: %d; skips: %d. Enumeration finished is not a completeness claim." %
          (result.get("containers_inspected", 0), result.get("parse_failures", 0), result.get("limits_hit", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
