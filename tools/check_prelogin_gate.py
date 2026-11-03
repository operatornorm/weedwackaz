"""Validate only the bounded prelogin report; it cannot authorize game staging."""
import argparse
import json
from pathlib import Path
import re


def check(raw,manifest):
    if not isinstance(raw,bytes) or len(raw)>512:
        raise ValueError('missing or oversized gate')
    if type(manifest.get('schema')) is not int or manifest['schema']!=1:
        raise ValueError('unsupported manifest')
    run=manifest.get('run','');tag=manifest.get('prelogin_sha256','')
    if not isinstance(run,str) or not re.fullmatch('[0-9a-f]{32}',run) or run=='0'*32:
        raise ValueError('invalid run')
    if not isinstance(tag,str) or not re.fullmatch('[0-9a-f]{64}',tag):
        raise ValueError('invalid source tag')
    pattern=b'WWQA1\n'+run.encode()+b'\n([0-9a-f]{32})\nprelogin\n'+tag.encode()+b'\n1,1,1,1\n'
    match=re.fullmatch(pattern,raw)
    if not match or match[1]==b'0'*32:
        raise ValueError('wrong stage/run/source tag or incomplete observations')
    return {'schema':1,'stage':'prelogin','result':'observations_accepted','run_id':run,
        'guest_session_id':match[1].decode(),'source_tag':tag,'executed_source_attested':False,
        'login_authorized':False,'offline_verified':False,'game_staging_authorized':False,'co_op_verified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(check(args.report.read_bytes(),json.loads(args.manifest.read_text(encoding='utf-8-sig'))),indent=2))


if __name__=='__main__':main()
