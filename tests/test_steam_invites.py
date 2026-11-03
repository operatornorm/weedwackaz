import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('DYNAMITE_SOURCE_DIR',str(ROOT.parent/'dynamite')))


class SteamInviteTests(unittest.TestCase):
    def fixture(self,mutate=None):
        with tempfile.TemporaryDirectory(prefix='ww-invites-') as directory:
            target=Path(directory)
            for filename in ('SteamInviteProtocol.h','SteamInviteBindings.h','SteamInviteProbe.h'):
                value=(SOURCE/'hook/src'/filename).read_text()
                if mutate:value=mutate(filename,value)
                (target/filename).write_text(value)
            command=['g++','-std=c++23','-Wall','-Wextra','-Werror','-pedantic','-pthread','-I',str(target),'-I',str(ROOT/'tests'),
                str(ROOT/'tests/dynamite_steam_invites.cpp'),str(SOURCE/'hook/src/SteamInviteProbe.cpp'),'-o',str(target/'fixture')]
            build=subprocess.run(command,capture_output=True,text=True,timeout=60)
            self.assertEqual(build.returncode,0,build.stderr)
            return subprocess.run([str(target/'fixture')],capture_output=True,text=True,timeout=15)

    def test_production_bindings_protocol_callback_queue_and_gates(self):
        result=self.fixture();self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PASS:',result.stdout)

    def test_wrong_app_guard_mutation_is_rejected(self):
        def mutate(name,value):
            if name=='SteamInviteBindings.h':
                needle='if (api.appId(utils) != AppId)'
                self.assertEqual(value.count(needle),1)
                return value.replace(needle,'if (api.appId(utils) == 0)')
            return value
        result=self.fixture(mutate);self.assertNotEqual(result.returncode,0);self.assertIn('wrong runtime AppID',result.stderr)

    def test_payload_expiry_mutation_is_rejected(self):
        def mutate(name,value):
            if name=='SteamInviteProtocol.h':
                needle='result.expires <= unixSeconds'
                self.assertEqual(value.count(needle),1)
                return value.replace(needle,'result.expires < unixSeconds')
            return value
        result=self.fixture(mutate);self.assertNotEqual(result.returncode,0);self.assertIn('expired or excessive lifetime',result.stderr)


if __name__=='__main__':unittest.main()
