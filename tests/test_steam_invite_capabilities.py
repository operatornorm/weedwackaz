import copy
import json
from pathlib import Path
import re
import sys
import os
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
SOURCE=Path(os.environ.get('DYNAMITE_SOURCE_DIR',str(ROOT.parent/'dynamite')))
from check_steam_invite_capabilities import check,PINS


def report():
    p=json.loads(PINS.read_bytes());names=p['required_exports']+[f'SteamFixture_{i}' for i in range(p['reported_steam_exports']-len(p['required_exports']))]
    return {'schema':1,'kind':'mgsv_steam_capabilities','read_only':True,'can_install':False,'runtime_interfaces_verified':False,'invite_callbacks_verified':False,
        'executable_sha256':p['executable_sha256'],'steam_api64':{'sha256':p['steam_dll_sha256'],'size':p['steam_dll_size'],'machine':'amd64',
        'named_export_count':p['reported_named_exports'],'steam_exports':names,'interface_string_candidates':p['factory_versions']}}


class SteamInviteCapabilitiesTests(unittest.TestCase):
    def test_complete_metadata_is_not_runtime_or_gameplay_proof(self):
        result=check(report());self.assertEqual(result['required_exports'],12)
        self.assertFalse(result['can_enable_gameplay']);self.assertFalse(result['runtime_interfaces_verified'])

    def test_fingerprint_counts_and_boolean_coercion_are_rejected(self):
        cases=[]
        d=report();d['executable_sha256']='0'*64;cases.append(d)
        d=report();d['steam_api64']['sha256']='0'*64;cases.append(d)
        d=report();d['read_only']=1;cases.append(d)
        d=report();d['runtime_interfaces_verified']=True;cases.append(d)
        d=report();d['steam_api64']['named_export_count']+=1;cases.append(d)
        for d in cases:
            with self.subTest(d=d.get('read_only')),self.assertRaises(ValueError):check(d)

    def test_each_required_function_and_version_candidate_is_required(self):
        p=json.loads(PINS.read_bytes())
        for name in p['required_exports']:
            d=report();d['steam_api64']['steam_exports'].remove(name);d['steam_api64']['steam_exports'].append('SteamFixtureReplacement')
            with self.subTest(symbol=name),self.assertRaisesRegex(ValueError,'required_export_missing'):check(d)
        for name in p['factory_versions']:
            d=report();d['steam_api64']['interface_string_candidates'].remove(name)
            with self.subTest(version=name),self.assertRaisesRegex(ValueError,'interface_candidate_missing'):check(d)

    def test_native_source_symbols_and_pins_agree(self):
        source=SOURCE/'hook/src/SteamInviteBindings.h'
        names=re.findall(r'WW_STEAM_BIND\(\w+, "([A-Za-z0-9_]+)"\)',source.read_text())
        p=json.loads(PINS.read_bytes());self.assertEqual(sorted(names),sorted(p['required_exports']))
        protocol=(SOURCE/'hook/src/SteamInviteProtocol.h').read_text()
        self.assertIn(p['executable_sha256'],protocol);self.assertIn(p['steam_dll_sha256'],protocol)
