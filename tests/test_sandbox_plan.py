import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


class SandboxPlanTests(unittest.TestCase):
    def fixture(self,mutate=None,mode=None):
        with tempfile.TemporaryDirectory(prefix='ww-sandbox-plan-') as directory:
            root=Path(directory)
            source=(ROOT/'tools/windows-sandbox-check/Plan.h').read_text()
            if mutate:source=mutate(source)
            (root/'Plan.h').write_text(source)
            binary=root/'plan'
            built=subprocess.run([os.environ.get('CXX','g++'),'-std=c++23','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(root),str(ROOT/'tests/sandbox_plan.cpp'),'-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stderr)
            return subprocess.run([str(binary)]+([mode] if mode else []),capture_output=True,text=True,timeout=15)

    def assert_configuration(self,text):
        root=ET.fromstring(text)
        self.assertEqual(root.tag,'Configuration')
        self.assertEqual([node.tag for node in root],['VGpu','Networking','AudioInput','VideoInput','PrinterRedirection',
            'ClipboardRedirection','MemoryInMB','MappedFolders','LogonCommand'])
        for tag in ('Networking','AudioInput','VideoInput','PrinterRedirection','ClipboardRedirection'):
            self.assertEqual(root.findtext(tag),'Disable')
        self.assertEqual(root.findtext('VGpu'),'Enable')
        self.assertEqual(root.findtext('MemoryInMB'),'4096')
        mappings=root.findall('./MappedFolders/MappedFolder')
        self.assertEqual(len(mappings),2,'exactly two bounded mappings required')
        for node,(host,guest,read_only) in zip(mappings,[(r'C:\case & test\Input',r'C:\MGSVQA\Input','true'),
            (r'C:\case & test\Output',r'C:\MGSVQA\Output','false')]):
            self.assertEqual([child.tag for child in node],['HostFolder','SandboxFolder','ReadOnly'])
            self.assertEqual((node.findtext('HostFolder'),node.findtext('SandboxFolder'),node.findtext('ReadOnly')),
                (host,guest,read_only))
        self.assertEqual(root.findtext('./LogonCommand/Command'),r'"C:\MGSVQA\Input\ww-sandbox-check.exe" --guest '+'a'*32)

    def test_exact_mapping_policy_and_guest_command(self):
        result=self.fixture(mode='--config')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assert_configuration(result.stdout)

    def test_broad_extra_mapping_mutation_is_rejected(self):
        def mutate(value):
            needle='L"</MappedFolders><LogonCommand>'
            self.assertEqual(value.count(needle),1)
            return value.replace(needle,'L"<MappedFolder><HostFolder>C:\\\\Users</HostFolder><SandboxFolder>C:\\\\Broad</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder></MappedFolders><LogonCommand>')
        result=self.fixture(mutate,mode='--config')
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaisesRegex(AssertionError,'exactly two bounded mappings'):
            self.assert_configuration(result.stdout)

    def test_production_plan_and_report_validation(self):
        result=self.fixture();self.assertEqual(result.returncode,0,result.stderr)

    def test_stale_nonce_mutation_is_rejected(self):
        def mutate(value):
            needle='packet.nonce==nonce'
            self.assertEqual(value.count(needle),1)
            return value.replace(needle,'nonce==nonce')
        result=self.fixture(mutate)
        self.assertNotEqual(result.returncode,0);self.assertIn('stale nonce rejected',result.stderr)

    def test_missing_observation_mutation_is_rejected(self):
        def mutate(value):
            needle='packet.flags==AllFlags'
            self.assertEqual(value.count(needle),1)
            return value.replace(needle,'packet.flags<=AllFlags')
        result=self.fixture(mutate)
        self.assertNotEqual(result.returncode,0);self.assertIn('missing observation blocks PASS',result.stderr)


if __name__=='__main__':unittest.main()
