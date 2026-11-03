"""Exercise production lifecycle bodies and the production-used sync tracker."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(os.environ.get(
    "DYNAMITE_SOURCE_DIR", str(Path(__file__).resolve().parents[2] / "dynamite")))
HEADER = SOURCE / "hook/src/DynamiteSyncImpl/InitialVarSync.h"
FIXTURE = Path(__file__).with_name("dynamite_initial_sync.cpp")


def method(source, name):
    start = source.index("    " + name)
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


class InitialSyncTests(unittest.TestCase):
    def run_fixture(self, header=None, mutation=None):
        compiler = os.environ.get("CXX", "g++")
        if not shutil.which(compiler):
            self.fail("A host C++ compiler is required; native checks did not run")
        source = (SOURCE / "hook/src/DynamiteSyncImpl/DynamiteSyncImpl.cpp").read_text()
        methods = "\n".join(method(source, signature) for signature in (
            "void DynamiteSyncImpl::SyncInit()", "void DynamiteSyncImpl::Init()",
            "void DynamiteSyncImpl::Stop()", "bool DynamiteSyncImpl::IsSynchronized()"))
        if mutation:
            methods = mutation(methods)
        with tempfile.TemporaryDirectory(prefix="ww-sync-") as directory:
            root = Path(directory)
            target = root / "DynamiteSyncImpl/InitialVarSync.h"
            target.parent.mkdir()
            target.write_text(header if header is not None else HEADER.read_text())
            fixture = root / "sync.cpp"
            fixture.write_text(FIXTURE.read_text().replace("__SYNC_METHODS__", methods))
            binary = root / "sync-test"
            build = subprocess.run([compiler, "-std=c++23", "-Wall", "-Wextra", "-Werror",
                                    "-pedantic", "-pthread", "-I", str(root), str(fixture),
                                    "-o", str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)

    def test_production_initial_sync_lifecycle(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS:", result.stdout)

    def test_old_empty_map_readiness_mutation_is_caught(self):
        original = HEADER.read_text()
        self.assertEqual(original.count("!status.empty() && "), 1)
        result = self.run_fixture(original.replace("!status.empty() && ", ""))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fresh state is not synchronized", result.stderr)

    def test_missing_stop_invalidation_mutation_is_caught(self):
        def mutate(methods):
            stop = methods.index("void DynamiteSyncImpl::Stop()")
            prefix, suffix = methods[:stop], methods[stop:]
            self.assertIn("initialVarSync.Reset();", suffix)
            return prefix + suffix.replace("initialVarSync.Reset();", "", 1)
        result = self.run_fixture(mutation=mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Stop invalidates completed tracking", result.stderr)


if __name__ == "__main__":
    unittest.main()
