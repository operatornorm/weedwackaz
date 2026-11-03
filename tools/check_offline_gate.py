"""Score a single local guest network-cut observation, never game authorization."""
import argparse
import json
from pathlib import Path
import re


def check(raw,request,prelogin):
    keys={'schema','stage','run','session','challenge','source_tag'}
    if not isinstance(request,dict) or set(request)!=keys or type(request.get('schema')) is not int or request['schema']!=1 or request.get('stage')!='offline-v1':
        raise ValueError('invalid request schema')
    for key,size in (('run',32),('session',32),('challenge',32),('source_tag',64)):
        value=request.get(key)
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}',value) or value=='0'*size:
            raise ValueError('invalid request '+key)
    if prelogin.get('result')!='observations_accepted' or request['run']!=prelogin.get('run_id') or request['session']!=prelogin.get('guest_session_id'):
        raise ValueError('wrong prelogin session')
    if not isinstance(raw,bytes) or len(raw)>512:
        raise ValueError('oversized or missing report')
    expected=('WWQA2\n'+request['run']+'\n'+request['session']+'\n'+request['challenge']+'\noffline\n'+request['source_tag']+'\n1,1,1,1,1,1\n').encode()
    if raw!=expected:
        raise ValueError('stale, wrong phase or incomplete offline report')
    return {'schema':1,'stage':'offline','result':'local_network_cut_observations_accepted',
        'run_id':request['run'],'guest_session_id':request['session'],'challenge':request['challenge'],
        'point_in_time_only':True,'executed_source_attested':False,'all_network_isolation_verified':False,
        'offline_license_verified':False,'game_staging_authorized':False,'game_launch_authorized':False,
        'multiplayer_verified':False,'co_op_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--request',type=Path,required=True)
    p.add_argument('--prelogin',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(check(a.report.read_bytes(),json.loads(a.request.read_text(encoding='utf-8-sig')),json.loads(a.prelogin.read_text())),indent=2))


if __name__=='__main__':main()
