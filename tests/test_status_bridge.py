import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_dynamite_lifecycle import Lua

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mgsv_observer_smoke as smoke
SOURCE=Path(os.environ.get('DYNAMITE_SOURCE_DIR',str(ROOT.parent/'dynamite')))


def sample(frame=1,run_id='a'*32):
    return {'schema':1,'kind':'mgsv_observer_status','observation_only':True,'can_authorize':False,'caller_affinity_checked':True,
        'run_id':run_id,'generation':'1','frame_id':str(frame),'publisher_tick_ms':str(frame*500),
        'observation':{'schema':1,'observation_only':True,'can_authorize':False,'coherent_snapshot_verified':False,
        'native':{'status':'observed','native_available':True,'sample_counter_exhausted':False,'sample_id':str(frame)},
        'context':{'mission':30010,'location':10,'sequence_name':'Seq_Fixture_Free','prepare_finished':True,'not_playable':False,
            'world_center':{'x':0,'y':0,'z':0},'local_position':{'x':10,'y':20,'z':30}},'player_slots':{'slot0_present':True},
        'verification':{k:False for k in ('peer_liveness','player_realization','same_world','center_agreement','complete_initial_sync','protocol_epoch','playable_free_roam_contract','save_isolation')}}}


class StatusBridgeTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os,'mkfifo'),'FIFO only on POSIX')
    def test_fifo_status_is_rejected_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'status';os.mkfifo(path)
            with self.assertRaisesRegex(smoke.Blocked,'not_regular'):smoke.read_status(path)
    def test_actual_native_file_publisher_and_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            binary=Path(directory)/'fixture'
            result=subprocess.run(['g++','-std=c++23','-Wall','-Wextra','-Werror','-pedantic','-pthread','-I',str(SOURCE/'hook/src'),str(ROOT/'tests/dynamite_status_file.cpp'),'-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            run=subprocess.run([str(binary),str(Path(directory)/'dynamite/wwqa')],capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn('PASS:',run.stdout)

    def test_real_lua_poll_is_inert_when_disabled_and_bounds_output(self):
        lua=Lua();module=json.dumps(str(SOURCE/'moddata/standalone/WWRuntimeBridge.lua'))
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'encoded.json'
            lua.execute('local bridge=assert(loadfile('+module+'))()\nlocal outputPath='+json.dumps(str(output))+'\n'+r'''
local reads,writes=0,0
Dynamite={RuntimeObservationDue=function() return false end,PublishRuntimeObservation=function() writes=writes+1 end}
WWRuntimeObservation={schema=1,Snapshot=function() reads=reads+1;return {} end}
assert(not bridge.Poll() and reads==0 and writes==0)
Dynamite.RuntimeObservationDue=function() return true end
local output
Dynamite.PublishRuntimeObservation=function(text) output=text;writes=writes+1;local f=assert(io.open(outputPath,"wb"));f:write(text);f:close();return true end
WWRuntimeObservation.Snapshot=function() reads=reads+1;assert(not bridge.Poll());return {schema=1,text='a'..string.char(34,92,10,0,31),flag=false} end
assert(bridge.Poll() and writes==1 and reads==1)
WWRuntimeObservation.Snapshot=function() return {too_large=string.rep("a",257)} end
assert(not bridge.Poll() and writes==1)
local stopped=0;Dynamite.StopRuntimeObservation=function() stopped=stopped+1 end
bridge.Suspend();assert(stopped==1 and bridge.Init==nil and bridge.OnReload==nil and bridge.Update==nil)
''')
            self.assertEqual(json.loads(output.read_text()),{'schema':1,'flag':False,'text':'a"\\\n\x00\x1f'})

    def test_scorer_requires_advancing_frame_native_sample_and_matching_generation(self):
        scorer=smoke.Scorer('a'*32,30010)
        self.assertTrue(scorer.accept(json.dumps(sample()).encode()))
        self.assertFalse(scorer.accept(json.dumps(sample()).encode()))
        self.assertTrue(scorer.accept(json.dumps(sample(2)).encode()))
        for key,value in (('run_id','b'*32),('generation','2'),('frame_id','1')):
            data=sample(3);data[key]=value
            with self.subTest(key=key),self.assertRaises(smoke.Blocked):scorer.accept(json.dumps(data).encode())
        data=sample(3);data['observation']['native']['sample_id']='2'
        with self.assertRaisesRegex(smoke.Blocked,'nonadvancing'):scorer.accept(json.dumps(data).encode())

    def test_actual_update_reload_and_termination_place_bridge_after_work_and_before_teardown(self):
        lua=Lua();path=json.dumps(str(SOURCE/'moddata/standalone/TppMain.lua'))
        lua.execute(r'''
local calls={};local function record(v) calls[#calls+1]=v end
Tpp={IsTypeFunc=function(v) return type(v)=="function" end,_requireList={}}
TppScriptVars={};ScriptBlock={UpdateScriptsInScriptBlocks=function() record("scriptblocks") end};Mission={}
TppMission={Update=function() record("mission") end,UpdateForMissionLoad=function() record("load") end}
TppSequence={Update=function() record("sequence") end};TppSave={Update=function() record("save") end}
TppDemo={Update=function() record("demo") end};TppPlayer={Update=function() record("player") end}
script_loader={Update=function() record("keys") end}
WWRuntimeBridge={Poll=function() record("observe") end,Suspend=function() record("suspend") end}
TppGameStatus={IsSet=function() return false end};vars={missionCode=30010,locationCode=10}
local main=assert(loadfile(MAIN_PATH))()
main.SetUpdateFunction({sequence={OnUpdate=function() record("subscript") end}})
main.OnUpdate({})
local expected={"mission","sequence","save","demo","player","load","keys","subscript","scriptblocks","observe"}
assert(#calls==#expected);for i,v in ipairs(expected) do assert(calls[i]==v) end
calls={};assert(not pcall(main.OnReload,{sequence={OnLoad=function() record("reload");error("fixture end") end}}))
assert(#calls==2 and calls[1]=="suspend" and calls[2]=="reload")
calls={};main.OnTerminate({sequence={OnTerminate=function() record("terminate") end}})
assert(#calls==2 and calls[1]=="suspend" and calls[2]=="terminate")
'''.replace('MAIN_PATH',path))

    def test_scorer_rejects_solo_fallback_wrong_world_missing_unknown_and_claimed_verification(self):
        cases=[]
        data=sample();data['observation']['schema']=2;cases.append(data)
        data=sample();data['observation']['verification']['peer_liveness']=True;cases.append(data)
        data=sample();data['observation']['native']['native_available']=False;cases.append(data)
        data=sample();data['observation']['context']['mission']=30020;cases.append(data)
        data=sample();data['observation']['context']['not_playable']=True;cases.append(data)
        data=sample();del data['observation']['context']['world_center'];cases.append(data)
        data=sample();data['observation']['player_slots']['slot0_present']=False;cases.append(data)
        for data in cases:
            with self.subTest(data=data),self.assertRaises(smoke.Blocked):smoke.Scorer('a'*32,30010).accept(json.dumps(data).encode())

    def test_running_timer_cannot_make_frozen_status_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            status=Path(directory)/'status.json';status.write_text(json.dumps(sample()))
            clock=[0.0]
            def advance(seconds):clock[0]+=max(seconds,0.01)
            with patch.object(smoke.time,'monotonic',side_effect=lambda:clock[0]),patch.object(smoke.time,'sleep',side_effect=advance):
                report=smoke.run(status,'a'*32,30010,5)
            self.assertEqual(report['result'],'BLOCKED');self.assertEqual(report['reason'],'stale_status')
            self.assertFalse(report['co_op_verified'])

    def test_live_native_publications_pass_only_observer_scope_and_late_freeze_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            status=Path(directory)/'status.json'
            for freeze in (False,True):
                clock=[0.0];frame=[1];status.write_text(json.dumps(sample()))
                def advance(seconds):
                    clock[0]+=max(seconds,0.01)
                    if not freeze or clock[0]<2:
                        frame[0]+=1;status.write_text(json.dumps(sample(frame[0])))
                with patch.object(smoke.time,'monotonic',side_effect=lambda:clock[0]),patch.object(smoke.time,'sleep',side_effect=advance):
                    report=smoke.run(status,'a'*32,30010,5)
                self.assertEqual(report['result'],'BLOCKED' if freeze else 'PASS')
                self.assertFalse(report['co_op_verified'])


if __name__=='__main__':unittest.main()
