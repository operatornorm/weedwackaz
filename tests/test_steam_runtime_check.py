import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('DYNAMITE_SOURCE_DIR',str(ROOT.parent/'dynamite')))


class SteamRuntimeCheckTests(unittest.TestCase):
    def test_actual_standalone_pipeline_with_fake_sdk(self):
        with tempfile.TemporaryDirectory(prefix='ww-steam-runtime-') as directory:
            binary=Path(directory)/'check'
            result=subprocess.run([os.environ.get('CXX','g++'),'-std=c++23','-Wall','-Wextra','-Werror','-pedantic','-pthread',
                '-I',str(SOURCE/'hook/src'),'-I',str(ROOT/'tests'),'-I',str(ROOT/'tools/steam-runtime-check'),
                str(ROOT/'tests/dynamite_steam_runtime_check.cpp'),'-o',str(binary)],text=True,capture_output=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(binary)],text=True,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('PASS:',result.stdout)


if __name__=='__main__':unittest.main()
