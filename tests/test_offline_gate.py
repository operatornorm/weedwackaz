from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_offline_gate import check


class OfflineGateTests(unittest.TestCase):
    def setUp(self):
        self.request={'schema':1,'stage':'offline-v1','run':'a'*32,'session':'b'*32,'challenge':'c'*32,'source_tag':'d'*64}
        self.prelogin={'result':'observations_accepted','run_id':'a'*32,'guest_session_id':'b'*32}
        self.raw=('WWQA2\n'+'a'*32+'\n'+'b'*32+'\n'+'c'*32+'\noffline\n'+'d'*64+'\n1,1,1,1,1,1\n').encode()

    def test_exact_observations_grant_no_game_licensing_or_multiplayer_authority(self):
        result=check(self.raw,self.request,self.prelogin)
        self.assertTrue(result['point_in_time_only'])
        for field in ('executed_source_attested','all_network_isolation_verified','offline_license_verified',
            'game_staging_authorized','game_launch_authorized','multiplayer_verified','co_op_verified'):
            self.assertIs(result[field],False)

    def test_stale_phase_session_challenge_and_partial_reports_reject(self):
        bad=(b'',self.raw+b'extra',self.raw.replace(b'offline',b'prelogin'),self.raw.replace(b'b'*32,b'e'*32),
            self.raw.replace(b'c'*32,b'e'*32),self.raw.replace(b'd'*64,b'e'*64),self.raw.replace(b'1,1,1,1,1,1',b'1,1,0,1,1,1'),b'x'*513)
        for raw in bad:
            with self.subTest(raw=raw),self.assertRaises(ValueError):check(raw,self.request,self.prelogin)

    def test_wrong_request_and_replacement_guest_reject(self):
        for delta in ({'schema':True},{'stage':'prelogin'},{'session':'e'*32},{'challenge':'0'*32},{'extra':1}):
            with self.subTest(delta=delta),self.assertRaises(ValueError):check(self.raw,{**self.request,**delta},self.prelogin)


if __name__=='__main__':unittest.main()
