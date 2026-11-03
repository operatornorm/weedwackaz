"""Build and exercise the production-used bounds header with the host C++ compiler."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(os.environ.get(
    "DYNAMITE_SOURCE_DIR", str(Path(__file__).resolve().parents[2] / "dynamite")))
FIXTURE = Path(__file__).with_name("dynamite_wire_bounds.cpp")


class WireBoundsTests(unittest.TestCase):
    def compile_and_run(self, include_dir, directory):
        compiler = os.environ.get("CXX", "g++")
        if not shutil.which(compiler):
            self.fail("Host C++ compiler unavailable; portable tests did not run")
        binary = Path(directory) / "wire-test"
        build = subprocess.run(
            [compiler, "-std=c++23", "-Wall", "-Wextra", "-Werror", "-pedantic",
             "-I", str(include_dir), str(FIXTURE), "-o", str(binary)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(build.returncode, 0, build.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)

    def test_production_payload_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.compile_and_run(SOURCE / "hook/src", directory)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("PASS:", run.stdout)

    def test_old_sender_size_mutation_is_rejected(self):
        header = SOURCE / "hook/src/DynamiteSyncImpl/WireBounds.h"
        text = header.read_text(encoding="utf-8")
        self.assertEqual(text.count("size <= MaxPayloadSize;"), 1)
        mutant = text.replace("size <= MaxPayloadSize;", "size <= MaxPayloadSize + HeaderSize;")
        with tempfile.TemporaryDirectory() as directory:
            include = Path(directory) / "include"
            dest = include / "DynamiteSyncImpl/WireBounds.h"
            dest.parent.mkdir(parents=True)
            dest.write_text(mutant, encoding="utf-8")
            run = self.compile_and_run(include, directory)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("old oversized sender window rejected", run.stderr)


if __name__ == "__main__":
    unittest.main()
