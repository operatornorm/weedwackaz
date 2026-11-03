#!/usr/bin/env python3
"""Extract the latest complete WW inventory from Dynamite's native log.

Uses only Python's standard library. Ignores unrelated log entries, checks frame
order/length/Adler-32 and the report footer, and refuses to overwrite output files.
Run before restarting MGSV: Dynamite truncates its native log at startup.
"""

import argparse
from pathlib import Path
import re
import sys
import zlib

MARKER = b"[lua] [WWINV1] "
MAX_BYTES = 512 * 1024
CHUNK_BYTES = 384
HEADER = re.compile(rb"(BEGIN|END) ([0-9]{1,20}-[0-9]{1,10}) ([0-9]{1,6}) ([0-9]{1,4}) ([0-9]{1,10})")
DATA = re.compile(rb"DATA ([0-9]{1,20}-[0-9]{1,10}) ([0-9]{1,4}) ([0-9a-f]+)")


def extract(lines):
    """Read log bytes; never return unrelated log text or an earlier partial run."""
    header = None
    report = bytearray()
    sequence = 0
    complete = False
    for line in lines:
        if MARKER not in line:
            continue
        if len(line) > 2048:
            raise ValueError("Inventory log frame exceeds the size limit")
        frame = line.partition(MARKER)[2].rstrip(b"\r\n")
        match = HEADER.fullmatch(frame)
        if match:
            kind, identity, length, count, checksum = match.groups()
            candidate = (identity, int(length), int(count), int(checksum))
            if not (0 < candidate[1] <= MAX_BYTES and
                    candidate[2] == (candidate[1] + CHUNK_BYTES - 1) // CHUNK_BYTES and
                    0 <= candidate[3] <= 0xFFFFFFFF):
                raise ValueError("Invalid inventory header")
            if kind == b"BEGIN":
                header = candidate
                report = bytearray()
                sequence = 0
                complete = False
                continue
            if (header != candidate or complete or sequence != candidate[2] or
                    len(report) != candidate[1] or zlib.adler32(report) != candidate[3]):
                raise ValueError("Inventory export is incomplete or its checksum does not match")
            complete = True
            continue
        match = DATA.fullmatch(frame)
        if not match or header is None or complete:
            raise ValueError("Invalid or misplaced inventory log frame")
        identity, index, encoded = match.groups()
        if (identity != header[0] or int(index) != sequence + 1 or
                sequence >= header[2] or len(encoded) % 2):
            raise ValueError("Inventory chunks are missing, duplicated or out of order")
        chunk = bytes.fromhex(encoded.decode("ascii"))
        expected = min(CHUNK_BYTES, header[1] - len(report))
        if len(chunk) != expected:
            raise ValueError("Inventory chunk length does not match its header")
        report.extend(chunk)
        sequence += 1
    if header is None:
        raise ValueError("No WW inventory found; collect in game before extracting")
    if not complete:
        raise ValueError("Latest inventory export is incomplete; no earlier report was substituted")
    result = bytes(report)
    if (not result.startswith(b"report.kind\truntime_metadata_only_not_a_gameplay_test\nreport.schema\t1\n") or
            not re.search(rb"\nreport.truncated\t(?:true|false)\nreport.complete\ttrue\n\Z", result)):
        raise ValueError("Inventory schema or completion footer is missing")
    result.decode("utf-8")
    if any(byte < 32 and byte not in (9, 10) for byte in result):
        raise ValueError("Unexpected control character in inventory report")
    if any(line.count(b"\t") != 1 for line in result.splitlines()):
        raise ValueError("Invalid inventory row")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="The co-op copy's dynamite/dynamite.log.txt")
    parser.add_argument("--output", type=Path, required=True, help="A new TSV filename")
    args = parser.parse_args(argv)
    try:
        with args.log.open("rb") as source:
            report = extract(source)
        with args.output.open("xb") as target:
            target.write(report)
    except (OSError, ValueError) as error:
        print("WW inventory: " + str(error), file=sys.stderr)
        return 1
    print("Saved runtime metadata: " + str(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
