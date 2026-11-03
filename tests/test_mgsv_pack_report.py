"""Safety checks for the standard-library, text-delivered archive reporter."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mgsv_pack_report as reporter


def container(name="/Assets/tpp/level_asset/chara/player/game_object/single_player2_instance.fox2"):
    data = bytearray(96)
    data[:10] = b"foxfpkdwin"
    struct.pack_into("<3I", data, 32, 2, 1, 0)
    encoded = name.encode()
    struct.pack_into("<I", data, 64, len(data))
    struct.pack_into("<I", data, 72, len(encoded))
    data.extend(encoded + b"\0")
    body = b"PRIVATE_ASSET_BODY_NEVER_EXPORT"
    struct.pack_into("<I", data, 48, len(data))
    struct.pack_into("<I", data, 56, len(body))
    data.extend(body)
    struct.pack_into("<I", data, 10, len(data))
    return bytes(data), body


def outer_encode(data, checksum, version=1, name_hash=0):
    data = bytearray(data)
    low = name_hash & 0xffffffff
    seed = int.from_bytes(checksum[(low % 2) * 8:(low % 2 + 1) * 8], "little") if version == 2 else 0
    for position in range(0, len(data), 8):
        index = 2 * ((low + seed + position // 11) % 4)
        mask = ((reporter.KEYS[index + 1] << 32) | reporter.KEYS[index]) ^ seed
        for j in range(min(8, len(data) - position)):
            data[position + j] ^= (mask >> (8 * j)) & 255
    return bytes(data)


class TextPackReporterTests(unittest.TestCase):
    def test_hash_length_limit_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "hash_name_length_limit"):
            reporter.city64(b"x" * 129)

    def test_allocation_metadata_fingerprints_without_exporting_body(self):
        data, body = container()
        result = reporter.inspect(data)
        self.assertTrue(result["members"][0]["allocation_candidate_by_name"])
        self.assertEqual(result["members"][0]["stored_member_sha256"], hashlib.sha256(body).hexdigest())
        self.assertNotIn("PRIVATE_ASSET_BODY", json.dumps(result))

    def test_unexpected_computer_paths_are_redacted(self):
        data, _ = container("C:/Users/PRIVATE_NAME/file.fox2")
        result = reporter.inspect(data)
        self.assertEqual(result["members"][0]["name"], "<name omitted>")
        self.assertNotIn("PRIVATE_NAME", json.dumps(result))

    def test_fpk_bounds_and_counts_are_checked(self):
        data, _ = container()
        for offset, value in ((36, 0xFFFFFFFF), (48, len(data)), (56, 0xFFFFFFFF),
                              (64, 0xFFFFFFFF), (72, 513), (10, 1)):
            with self.subTest(offset=offset):
                mutant = bytearray(data)
                struct.pack_into("<I", mutant, offset, value)
                with self.assertRaises(ValueError):
                    reporter.inspect(mutant)

    def test_qar_bounds_are_checked_before_large_allocations(self):
        data = bytearray(32)
        data[:4] = b"SQAR"
        struct.pack_into("<I", data, 8, 250001 ^ reporter.XOR[1])
        struct.pack_into("<I", data, 24, 2 ^ reporter.XOR[0])
        with self.assertRaisesRegex(ValueError, "qar_entry_limit"):
            reporter.index_archive(io.BytesIO(data), len(data))
        with self.assertRaises(ValueError):
            reporter.index_archive(io.BytesIO(data[:10]), 10)

    def test_container_limits_and_checksum_errors_stop_safely(self):
        entry = (0, 0, 8, 8, b"\0" * 16, 0)
        with self.assertRaisesRegex(ValueError, "checksum"):
            reporter.decode(io.BytesIO(b"12345678"), 8, 2, entry)
        too_large = (0, 0, reporter.MAX_PACK + 17, 8, b"\0" * 16, 0)
        with self.assertRaisesRegex(ValueError, "size_limit"):
            reporter.decode(io.BytesIO(b""), 0, 2, too_large)

    def test_both_digest_conventions_require_full_valid_decode(self):
        payload, _ = container()
        compressed = zlib.compress(payload)
        for version in (1, 2):
            for name_hash in (0, 1):
                for representation, stage in ((payload, "decoded_payload"), (compressed, "decrypted_stored")):
                    checksum = hashlib.md5(representation).digest()
                    encoded = outer_encode(compressed, checksum, version, name_hash)
                    entry = (name_hash, 0, len(encoded), len(payload), checksum, 0)
                    verification = {}
                    actual = reporter.decode(io.BytesIO(encoded), len(encoded), version, entry, verification)
                    self.assertEqual(actual, payload)
                    self.assertEqual(verification["checksum_stage"], stage)
                    if version == 2:
                        # Each half must be checked, including the half not used as a decryption seed.
                        for half in (0, 8):
                            bad = bytearray(checksum)
                            bad[half] ^= 1
                            with self.assertRaises((ValueError, zlib.error)):
                                reporter.decode(io.BytesIO(encoded), len(encoded), version,
                                                (name_hash, 0, len(encoded), len(payload), bytes(bad), 0))

        for label, raw, decoded_size in (
                ("adler32", compressed[:-1] + bytes([compressed[-1] ^ 1]), len(payload)),
                ("truncated", compressed[:-1], len(payload)),
                ("trailing", compressed + b"x", len(payload)),
                ("second_stream", compressed + compressed, len(payload)),
                ("length", compressed, len(payload) + 1)):
            with self.subTest(label=label):
                checksum = hashlib.md5(raw).digest()
                encoded = outer_encode(raw, checksum)
                with self.assertRaises((ValueError, zlib.error)):
                    reporter.decode(io.BytesIO(encoded), len(encoded), 1,
                                    (0, 0, len(encoded), decoded_size, checksum, 0))

    def test_failure_codes_and_partial_counts_do_not_leak_paths(self):
        self.assertEqual(reporter.failure_code(OSError("/home/PRIVATE_NAME/game/file")), "io_read_failed")
        self.assertEqual(reporter.failure_code(ValueError("PRIVATE_BODY")), "binary_structure_failed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "master").mkdir()
            (root / "mgsvtpp.exe").write_bytes(b"SYNTHETIC_EXECUTABLE")
            (root / "master/chunk0.dat").write_bytes(b"fixture")
            name = "/Assets/tpp/pack/mission2/free/f30020/f30020.fpk"
            entry = (reporter.path_hash(name), 0, 8, 8, b"\0" * 16, 0)
            with mock.patch.object(reporter, "seeds", return_value=[name]), \
                    mock.patch.object(reporter, "index_archive", return_value=(1, [entry])), \
                    mock.patch.object(reporter, "decode", side_effect=reporter.ReportError("container_checksum_mismatch")), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = reporter.collect(root)
            self.assertTrue(result["enumeration_finished"])
            self.assertEqual(result["containers_inspected"], 0)
            self.assertEqual(result["containers_failed"], 1)
            self.assertEqual(result["parse_failures"], 1)
            self.assertEqual(result["containers"][0]["failure_code"], "container_checksum_mismatch")
            self.assertNotIn(directory, json.dumps(result))

    def test_output_preservation_and_game_directory_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "copy"
            root.mkdir()
            output = Path(directory) / "report.json"
            messages = io.StringIO()
            with mock.patch.object(reporter, "collect", return_value={"kind": "metadata"}) as collect:
                with contextlib.redirect_stdout(messages), contextlib.redirect_stderr(messages):
                    self.assertEqual(reporter.main(["--game-dir", str(root), "--output", str(root / "forbidden.json")]), 1)
                    collect.assert_not_called()
                    self.assertEqual(reporter.main(["--game-dir", str(root), "--output", str(output)]), 0)
                    original = output.read_bytes()
                    self.assertEqual(reporter.main(["--game-dir", str(root), "--output", str(output)]), 1)
            self.assertEqual(output.read_bytes(), original)
            self.assertFalse((root / "forbidden.json").exists())


if __name__ == "__main__":
    unittest.main()
