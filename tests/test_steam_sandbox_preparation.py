import base64
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import prepare_steam_sandbox as prep


class SteamPreparationTests(unittest.TestCase):
    def test_interactive_guard_and_launch_form_one_invocation(self):
        commands=prep.guest_install_commands(prep.load_pin())
        self.assertTrue(commands.startswith('& {\n'))
        self.assertTrue(commands.endswith('\n}\n'))
        self.assertEqual(commands.count('Start-Process'),1)
        self.assertIn("    $ErrorActionPreference = 'Stop'",commands)
        self.assertLess(commands.index('Get-FileHash'),commands.index('Get-AuthenticodeSignature'))
        self.assertLess(commands.index('Get-AuthenticodeSignature'),commands.index('Start-Process'))

    def generated(self,root):
        folder=prep.generate(Path(root)/'new-profile')
        return folder,ET.fromstring((folder/'Steam-preparation.wsb').read_bytes())

    def test_online_profile_has_zero_host_mappings_and_disabled_redirects(self):
        with tempfile.TemporaryDirectory() as root:
            folder,xml=self.generated(root)
            self.assertEqual(xml.tag,'Configuration')
            self.assertEqual([e.tag for e in xml],['VGpu','Networking','AudioInput','VideoInput','PrinterRedirection',
                'ClipboardRedirection','MemoryInMB','LogonCommand'])
            self.assertIsNone(xml.find('.//MappedFolders'))
            self.assertIsNone(xml.find('.//HostFolder'))
            for tag in ('AudioInput','VideoInput','PrinterRedirection','ClipboardRedirection'):
                self.assertEqual(xml.findtext(tag),'Disable')
            self.assertEqual(xml.findtext('Networking'),'Enable')
            self.assertEqual(xml.findtext('MemoryInMB'),'4096')
            self.assertEqual(folder.name,'new-profile')

    def test_encoded_logon_roundtrips_source_and_instructions_as_data(self):
        with tempfile.TemporaryDirectory() as root:
            folder,xml=self.generated(root)
            command=xml.findtext('./LogonCommand/Command')
            prefix='C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoLogo -NoProfile -EncodedCommand '
            self.assertTrue(command.startswith(prefix))
            decoded=base64.b64decode(command[len(prefix):],validate=True).decode('utf-16le')
            self.assertEqual(decoded,(folder/'LOGON-SOURCE.ps1').read_text())
            match=re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)",decoded)
            self.assertIsNotNone(match)
            self.assertEqual(base64.b64decode(match[1],validate=True).decode('utf-8'),(folder/'GUEST-INSTRUCTIONS.txt').read_text())
            # Startup may only expose instructions/browser: no install, login,
            # policy changes, downloaded-code evaluation or feature commands.
            for forbidden in ('Invoke-Expression','ExecutionPolicy','Enable-WindowsOptionalFeature','SteamSetup.exe -',
                'Get-Credential','Get-Content','Get-FileHash','Get-AuthenticodeSignature'):
                self.assertNotIn(forbidden,decoded)

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            folder,_=self.generated(root)
            original={p.name:p.read_bytes() for p in folder.iterdir()}
            with self.assertRaises(FileExistsError):prep.generate(folder)
            self.assertEqual(original,{p.name:p.read_bytes() for p in folder.iterdir()})

    def test_unapproved_endpoint_or_invalid_pin_cannot_generate_profile(self):
        original=prep.load_pin()
        for change in ({'installer_url':'http://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe'},
            {'installer_url':'https://example.com/SteamSetup.exe'},{'installer_sha256':'0'*64},
            {'installer_sha256':'not-a-hash'},{'manifest_commit':'main'}):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as root:
                path=Path(root)/'bad.json';path.write_text(json.dumps({**original,**change}))
                with self.assertRaises(ValueError):prep.generate(Path(root)/'profile',path)


if __name__=='__main__':unittest.main()
