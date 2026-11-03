"""Exercise native-log framing, incomplete captures, privacy and output preservation."""

import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from extract_ww_inventory import CHUNK_BYTES, MAX_BYTES, extract, main

REPORT = (
    b"report.kind\truntime_metadata_only_not_a_gameplay_test\n"
    b"report.schema\t1\n"
    b"quests.questList.name\truins_q19010\n"
    b"report.truncated\tfalse\nreport.complete\ttrue\n"
)


def frames(report=REPORT, identity=b"123-1"):
    chunks = [report[i:i + CHUNK_BYTES] for i in range(0, len(report), CHUNK_BYTES)]
    header = b"%s %d %d %d" % (identity, len(report), len(chunks), zlib.adler32(report))
    records = [b"BEGIN " + header]
    records.extend(b"DATA %s %d %s" % (identity, index, chunk.hex().encode("ascii"))
                   for index, chunk in enumerate(chunks, 1))
    records.append(b"END " + header)
    return [b"[timestamp] [dynamite] [info] [lua] [WWINV1] " + row + b"\n"
            for row in records]


class ExtractInventoryTests(unittest.TestCase):
    def test_unrelated_private_log_entries_are_excluded(self):
        log = [b"SECRET_NATIVE_PATH SteamID 1234567 address 192.0.2.1\n"]
        for row in frames():
            log.extend([row, b"UNRELATED_SECRET between frames\n"])
        self.assertEqual(extract(log), REPORT)
        self.assertNotIn(b"SECRET", extract(log))

    def test_missing_duplicate_or_reordered_chunks_are_rejected(self):
        report = REPORT.replace(b"quests.questList.name", b"key\tvalue\n" * 120 + b"quests.questList.name")
        rows = frames(report)
        self.assertGreater(len(rows), 4)
        for mutation in (rows[:1] + rows[2:], rows[:2] + rows[1:],
                         rows[:1] + [rows[2], rows[1]] + rows[3:]):
            with self.subTest(mutation=mutation[:1]):
                with self.assertRaises(ValueError):
                    extract(mutation)

    def test_checksum_mismatch_is_rejected(self):
        rows = frames()
        rows[1] = rows[1].replace(REPORT[:1].hex().encode("ascii"), b"00", 1)
        with self.assertRaisesRegex(ValueError, "checksum"):
            extract(rows)

    def test_truncated_capture_is_rejected(self):
        for rows in (frames()[:-1], frames()[1:]):
            with self.assertRaises(ValueError):
                extract(rows)

    def test_latest_incomplete_run_does_not_substitute_an_earlier_report(self):
        with self.assertRaisesRegex(ValueError, "Latest inventory export is incomplete"):
            extract(frames() + frames(identity=b"123-2")[:-1])

    def test_latest_complete_capture_is_selected(self):
        latest = REPORT.replace(b"ruins_q19010", b"ruins_q19011")
        self.assertEqual(extract(frames() + frames(latest, b"123-2")), latest)

    def test_invalid_or_oversized_headers_are_rejected(self):
        for header in (b"123-1 0 0 0", b"123-1 %d 1366 0" % (MAX_BYTES + 1),
                       b"123-1 20 2 0", b"123-1 20 1 9999999999"):
            with self.assertRaises(ValueError):
                extract([b"[lua] [WWINV1] BEGIN " + header + b"\n"])

    def test_missing_schema_or_footer_is_rejected_even_with_valid_checksum(self):
        for payload in (REPORT.replace(b"report.schema\t1\n", b""),
                        REPORT.replace(b"report.complete\ttrue", b"report.complete\tfalse")):
            with self.assertRaises(ValueError):
                extract(frames(payload))

    def test_invalid_hex_and_extra_data_after_end_are_rejected(self):
        bad_hex = frames()
        bad_hex[1] = bad_hex[1][:-3] + b"zz\n"
        for rows in (bad_hex, frames() + [frames()[1]]):
            with self.assertRaises(ValueError):
                extract(rows)

    def test_no_inventory_does_not_echo_raw_log(self):
        with self.assertRaisesRegex(ValueError, "^No WW inventory found"):
            extract([b"PRIVATE_USER SteamID SECRET\n"])

    def test_cli_writes_report_and_preserves_an_existing_output(self):
        with tempfile.TemporaryDirectory(prefix="ww-extract-") as directory:
            root = Path(directory)
            log, output = root / "native.log", root / "report.tsv"
            log.write_bytes(b"SECRET_NATIVE_ENTRY\n" + b"".join(frames()))
            command = [sys.executable, str(ROOT / "tools/extract_ww_inventory.py"),
                       str(log), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes(), REPORT)
            output.write_bytes(b"keep this prior report")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(output.read_bytes(), b"keep this prior report")
            self.assertNotIn("SECRET_NATIVE_ENTRY", result.stdout + result.stderr)

    def test_invalid_capture_creates_no_output_and_does_not_print_raw_log(self):
        with tempfile.TemporaryDirectory(prefix="ww-extract-") as directory:
            root = Path(directory)
            log, output = root / "native.log", root / "report.tsv"
            log.write_bytes(b"PRIVATE_NATIVE_ENTRY\n" + b"".join(frames()[:-1]))
            messages = io.StringIO()
            with contextlib.redirect_stdout(messages), contextlib.redirect_stderr(messages):
                self.assertEqual(main([str(log), "--output", str(output)]), 1)
            self.assertFalse(output.exists())
            self.assertNotIn("PRIVATE_NATIVE_ENTRY", messages.getvalue())


if __name__ == "__main__":
    unittest.main()
