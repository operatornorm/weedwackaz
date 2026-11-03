from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_prelogin_gate import check


class PreloginGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'schema':1,'run':'a'*32,'prelogin_sha256':'b'*64}
        self.raw=('WWQA1\n'+'a'*32+'\n'+'c'*32+'\nprelogin\n'+'b'*64+'\n1,1,1,1\n').encode()

    def test_exact_observations_have_no_login_offline_or_game_authority(self):
        result=check(self.raw,self.manifest)
        self.assertEqual(result['guest_session_id'],'c'*32)
        for field in ('executed_source_attested','login_authorized','offline_verified','game_staging_authorized','co_op_verified'):
            self.assertIs(result[field],False)

    def test_stale_incomplete_wrong_phase_and_extra_fields_reject(self):
        bad=(b'',self.raw+b'extra\n',self.raw.replace(b'prelogin',b'offline'),self.raw.replace(b'1,1,1,1',b'1,1,0,1'),
            self.raw.replace(b'a'*32,b'd'*32),self.raw.replace(b'b'*64,b'e'*64),self.raw.replace(b'c'*32,b'0'*32),b'x'*513)
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):check(value,self.manifest)

    def test_invalid_manifest_cannot_authorize_a_report(self):
        for delta in ({'schema':True},{'run':'0'*32},{'run':'bad'},{'prelogin_sha256':'bad'}):
            with self.subTest(delta=delta),self.assertRaises(ValueError):check(self.raw,{**self.manifest,**delta})


if __name__=='__main__':unittest.main()
