import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mgsv_steam_capabilities as probe


def fixture():
    data=bytearray(2048)
    def w16(off,value):struct.pack_into('<H',data,off,value)
    def w32(off,value):struct.pack_into('<I',data,off,value)
    data[:2]=b'MZ';w32(0x3c,0x80);data[0x80:0x84]=b'PE\0\0'
    w16(0x84,0x8664);w16(0x86,1);w16(0x94,240)
    optional=0x98;w16(optional,0x20b);w32(optional+108,16);w32(optional+112,0x1000);w32(optional+116,0x200)
    section=optional+240;w32(section+12,0x1000);w32(section+16,0x600);w32(section+20,0x200)
    names=['SteamAPI_Init','SteamAPI_RegisterCallback','SteamClient','UnrelatedExport']
    w32(0x200+24,len(names));w32(0x200+32,0x1040)
    for i,name in enumerate(names):
        w32(0x240+i*4,0x1080+i*48)
        b=name.encode()+b'\0';data[0x280+i*48:0x280+i*48+len(b)]=b
    versions=b'\0SteamFriends015\0SteamClient017\0SteamMatchMaking009\0'
    data[0x600:0x600+len(versions)]=versions
    return bytes(data)


class SteamCapabilitiesTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os,'mkfifo'),'FIFO only on POSIX')
    def test_nonregular_executable_is_rejected_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);os.mkfifo(game/'mgsvtpp.exe')
            with self.assertRaisesRegex(probe.Invalid,'size_or_type'):probe.report(game)
    def test_bounded_pe_exports_and_interface_candidates_without_loading(self):
        result=probe.exports(fixture())
        self.assertEqual(result['machine'],'amd64')
        self.assertEqual(result['named_export_count'],4)
        self.assertEqual(result['steam_exports'],['SteamAPI_Init','SteamAPI_RegisterCallback','SteamClient'])
        self.assertEqual(result['interface_string_candidates'],['SteamClient017','SteamFriends015','SteamMatchMaking009'])

    def test_game_interface_candidates_cross_chunk_boundary_without_exporting_other_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.exe'
            path.write_bytes(b'\0'*(1048576-5)+b'SteamFriends015\0PRIVATE_DO_NOT_EXPORT\0SteamUser018\0')
            self.assertEqual(probe.interface_candidates(path),['SteamFriends015','SteamUser018'])
            prefix=b'SteamClient017'
            path.write_bytes(b'\0'*(1048576-len(prefix))+prefix+b'X\0SteamFriends015\0')
            self.assertEqual(probe.interface_candidates(path),['SteamFriends015'])

    def test_malformed_headers_tables_counts_and_strings_fail_closed(self):
        cases=[b'',fixture()[:128]]
        for offset,value in ((0x3c,0xfffffffe),(0x200+24,16385),(0x200+32,0xffffff00),(0x240,0xffffff00),(0x98+112,0)):
            data=bytearray(fixture());struct.pack_into('<I',data,offset,value);cases.append(data)
        data=bytearray(fixture());data[0x280:0x301]=b'A'*129;cases.append(data)
        for data in cases:
            with self.subTest(size=len(data)),self.assertRaises(probe.Invalid):probe.exports(data)

    def test_report_is_metadata_only_and_never_changes_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);(game/'mgsvtpp.exe').write_bytes(b'synthetic exe');(game/'steam_api64.dll').write_bytes(fixture())
            before={p.name:p.read_bytes() for p in game.iterdir()}
            with patch.object(probe,'sha256',return_value=probe.EXE_SHA256): report=probe.report(game)
            self.assertEqual(before,{p.name:p.read_bytes() for p in game.iterdir()})
            text=json.dumps(report)
            self.assertNotIn(directory,text);self.assertNotIn('synthetic exe',text)
            self.assertEqual(report['steam_api64']['sha256'],hashlib.sha256(fixture()).hexdigest())
            self.assertTrue(report['read_only']);self.assertFalse(report['can_install']);self.assertFalse(report['runtime_interfaces_verified'])

    def test_wrong_executable_identity_stops_before_dll_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);(game/'mgsvtpp.exe').write_bytes(b'wrong exe')
            with self.assertRaisesRegex(probe.Invalid,'executable_fingerprint_mismatch'):probe.report(game)


if __name__=='__main__':unittest.main()
