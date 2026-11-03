"""Execute the real Lua adapter and loader callbacks with engine/provider stubs.

Providers below are explicit fixtures. No native proof producer or game QA is
supplied by these tests, and production registers no providers.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_dynamite_lifecycle import Lua

SOURCE = Path(os.environ.get("DYNAMITE_SOURCE_DIR", str(Path(__file__).resolve().parents[2] / "dynamite")))
LIB = SOURCE / "moddata/standalone"
BASE = "7fe74d31128ed8d3741b07181cb99e4adc1f57be"


def fixture(extra):
    code = r'''
local calls = {}
local function record(name) calls[#calls+1] = name end
local function clear() calls = {} end
local function has(name) for _,v in ipairs(calls) do if v==name then return true end end return false end
local role, peerReady, members, demo, sample = "host", false, 1, false, 0
local packageHook, runtimeHook, acceptHook, targetHook, blockHook, stopHook
local lastPackage, lastRuntime
WWFreeRoamManifest = assert(loadfile(%MANIFEST%))()
local manifest = WWFreeRoamManifest
local w = assert(loadfile(%ADAPTER%))()
WWFreeRoam = w
Tpp = { IsTypeFunc=function(v) return type(v)=="function" end, IsTypeTable=function(v) return type(v)=="table" end,
        _requireList={} }
TppScriptVars, ScriptBlock, Mission = {}, {}, {}
vars = {missionCode=30010,locationCode=10}
local online = true
TppGameStatus = { IsSet=function() return online end, Reset=function() online=false; record("reset-online") end }
Dynamite = {
    IsHost=function() return role=="host" end,
    IgnoreMarkerRequests=function() record("ignore-markers") end,
    AcceptMarkerRequests=function() record("accept-markers") end,
    CreateHostSession=function() record("create-host") end,
    CreateClientSession=function() error("must never create client during load/start") end,
    ResetClientSessionState=function() record("reset-client") end,
    StartNearestEnemyThread=function() record("target"); if targetHook then return targetHook() end end,
    StopNearestEnemyThread=function() record("stop"); if stopHook then return stopHook() end end,
}
Vector3=function(x,y,z) return {x=x,y=y,z=z} end
TppCoder={SetWorldCenter=function(v) assert(v.x==10 and v.y==20 and v.z==30);record("center") end}
TppNetworkUtil={
    SessionEnableAccept=function(value)
        record(value and "accept" or "block")
        if value and acceptHook then return acceptHook() end
        if not value and blockHook then return blockHook() end
    end,
    SessionDisconnectPreparingMembers=function() record("disconnect") end,
    CloseSession=function() record("close") end,
}
local function find(id) for _,t in ipairs(manifest.targets) do if t.id==id then return t end end error("fixture target") end
local function echo(request)
    local p={};for k,v in pairs(request) do p[k]=v end;return p
end
local function packageProof(request)
    local p,t=echo(request),find(request.id)
    for _,flag in ipairs({"packages_verified","companion_routing_verified","dependencies_verified","profile_verified",
        "lifecycle_contract_verified","save_isolation_verified","protocol_epoch_verified"}) do p[flag]=true end
    p.manifest_sha256,p.executable_sha256=manifest.manifest_sha256,manifest.executable_sha256
    p.source_fpkd_sha256,p.loader_sha256,p.profile_hash=t.source_fpkd_sha256,t.source_loader_sha256,t.profile_hash
    p.package_path,p.companion_path=t.staged_fpk,t.staged_fpkd
    p.support_fpk,p.support_fpkd_sha256=manifest.support_fpk,manifest.support_fpkd_sha256
    p.output_fpkd_sha256,p.support_fpk_sha256=string.rep("a",64),string.rep("b",64)
    p.session_token,p.center_key=string.rep("d",64),string.rep("e",64)
    p.role,p.sequence_name,p.center=role,"Fixture_Playable",{x=10,y=20,z=30}
    p.connected_before_load=role=="client"
    if packageHook then packageHook(p,request) end
    lastPackage=p;return p
end
local function runtimeProof(request)
    local p=echo(request);sample=sample+1
    p.sample_id,p.role,p.is_demo,p.sequence_name=sample,role,demo,"Fixture_Playable"
    p.session_token,p.center_key=string.rep("d",64),string.rep("e",64)
    p.center_plan_verified,p.local_player_realized,p.session_created,p.connected=true,true,true,true
    p.member_count=members
    p.peer_live,p.same_world,p.center_agreed,p.initial_sync_ready=peerReady,peerReady,peerReady,peerReady
    p.remote_player_realized,p.players_realized=peerReady,peerReady and 2 or 1
    if runtimeHook then runtimeHook(p,request) end
    lastRuntime=p;return p
end
local provider={packages=packageProof,runtime=runtimeProof}
local function select(id)
    local t=find(id)
    local path,token=w.BeginPackageLoad(t.mission,t.location,t.branch,t.source_fpk)
    return t,path,token
end
local function selected(id)
    local t,path,token=select(id)
    assert(path==t.staged_fpk)
    assert(w.AppendSupport(token,function(path) assert(path==manifest.support_fpk);record("support") end))
    return t,token
end
local function allocated(id)
    local t,token=selected(id)
    assert(w.FreezeAllocation(t.mission,t.location))
    vars.missionCode,vars.locationCode=t.mission,t.location
    return t,token
end
local function prepared(id)
    local t,token=allocated(id)
    assert(w.ObserveInitialized(t.mission,t.location))
    assert(w.ObservePrepared(t.mission,t.location))
    assert(w.ObserveGameStarted(t.mission,t.location,true))
    return t,token
end
local main = assert(loadfile(%MAIN%))()
'''
    for token, path in (("%MANIFEST%", LIB / "WWFreeRoamManifest.lua"), ("%ADAPTER%", LIB / "WWFreeRoam.lua"),
                        ("%MAIN%", LIB / "TppMain.lua"), ("%LIST%", LIB / "TppMissionList.lua")):
        code = code.replace(token, json.dumps(str(path)))
    return code + "\n" + extra


class FreeRoamAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = Lua()

    def run_lua(self, code):
        self.lua.execute(fixture(code))

    def test_embedded_manifest_matches_pinned_inputs_and_unique_staged_namespace(self):
        generator_path = Path(__file__).resolve().parents[1] / "build-support/generate_free_roam_manifest.py"
        spec = importlib.util.spec_from_file_location("free_roam_manifest_generator", generator_path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        data = generator.build_data(SOURCE)
        expected = "-- Generated by build-support/generate_free_roam_manifest.py. Data only; never enables co-op.\nreturn " + generator.lua(data) + "\n"
        self.assertEqual((LIB / "WWFreeRoamManifest.lua").read_text(), expected)
        self.assertEqual(len(data["targets"]), 3)
        aliases = {target[key] for target in data["targets"] for key in ("staged_fpk", "staged_fpkd")}
        self.assertEqual(len(aliases), 6)
        self.assertTrue(all(path.startswith("/Assets/tpp/pack/coop/free/") for path in aliases))
        self.assertTrue(all(target["source_fpk"] not in aliases for target in data["targets"]))

    def test_default_and_plain_verified_flags_cannot_activate(self):
        self.run_lua(r'''
assert(w.Init==nil and w.OnReload==nil and w.DeclareSVars==nil and w.OnMessage==nil)
assert(not w.Configure(true,{packages_verified=true,dependencies_verified=true}))
for _,target in ipairs(manifest.targets) do
    local t,path,token=select(target.id)
    assert(path==t.source_fpk)
    assert(not w.AppendSupport(token,function() error("inactive added support") end))
    assert(not w.FreezeAllocation(t.mission,t.location))
    assert(not main.IsCoop(t.mission))
    assert(not w.TryStart(token))
    local termination=w.CaptureTermination();assert(not termination.needs_cleanup)
    assert(w.CompleteTermination(termination))
end
assert(#calls==0)
assert(main.IsCoop(10033))
''')

    def test_repeated_package_lists_each_get_one_support_and_active_state_is_separate(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
local t,first=selected("afghanistan-normal")
assert(not w.AppendSupport(first,function() error("duplicate support") end))
local _,second=selected("afghanistan-normal");assert(second>first)
assert(w.FreezeAllocation(t.mission,t.location))
assert(main.IsCoop(30010))
local before=w.Status().active_generation
local nextTarget,nextToken=selected("africa-normal")
assert(w.Status().active_generation==before and w.Status().pending_generation==nextToken)
assert(main.IsCoop(30010))
local old=w.CaptureTermination();assert(old.needs_cleanup)
assert(w.CompleteTermination(old))
assert(w.Status().pending_generation==nextToken)
assert(w.FreezeAllocation(nextTarget.mission,nextTarget.location))
vars.missionCode,vars.locationCode=30020,20
assert(main.IsCoop(30020) and not main.IsCoop(30010))
''')

    def test_mismatched_allocation_consumes_stale_pending_and_late_opt_in_is_blocked(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
local t,token=selected("afghanistan-normal")
assert(not w.FreezeAllocation(30020,20))
assert(w.Status().pending_generation==0)
assert(not w.Configure(true,provider))
local done=w.CaptureTermination();assert(w.CompleteTermination(done))
assert(not w.FreezeAllocation(30010,10))
assert(not w.IsCoopLoad(30010,10))
done=w.CaptureTermination();assert(w.CompleteTermination(done))
assert(w.Configure(true,provider))
''')

    def test_receipts_are_fresh_immutable_and_rechecked_before_allocation(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
local t,token=selected("afghanistan-normal")
lastPackage.center.x=999 -- selection kept a private copy
assert(w.FreezeAllocation(t.mission,t.location))
local done=w.CaptureTermination();assert(w.CompleteTermination(done))
local cached
packageHook=function(p,r) if not cached then cached=p else
    for k,v in pairs(cached) do r[k]=v end -- must not rewrite adapter's expected request
    for k,v in pairs(cached) do p[k]=v end
end end
local _,path=select("afghanistan-normal");assert(path==t.staged_fpk)
local _,path2=select("afghanistan-normal");assert(path2==t.source_fpk)
assert(not w.FreezeAllocation(t.mission,t.location))
done=w.CaptureTermination();assert(w.CompleteTermination(done))
packageHook=function(p,r) if r.phase=="allocation" then p.output_fpkd_sha256=string.rep("c",64) end end
selected("afghanistan-normal")
assert(not pcall(w.FreezeAllocation,t.mission,t.location))
assert(w.Status().phase=="allocation_rejected" and w.Status().cleanup_needed)
''')

    def test_each_missing_preflight_requirement_and_client_preconnection_blocks_selection(self):
        self.run_lua(r'''
for _,flag in ipairs({"packages_verified","companion_routing_verified","dependencies_verified","profile_verified",
    "lifecycle_contract_verified","save_isolation_verified","protocol_epoch_verified"}) do
    assert(w.Configure(true,provider))
    packageHook=function(p) p[flag]=false end
    local t,path,token=select("afghanistan-normal");assert(path==t.source_fpk)
    assert(not w.FreezeAllocation(t.mission,t.location))
    local done=w.CaptureTermination();assert(w.CompleteTermination(done))
end
role="client";assert(w.Configure(true,provider))
packageHook=function(p) p.connected_before_load=false end
local t,path=select("afghanistan-normal");assert(path==t.source_fpk)
assert(not w.FreezeAllocation(t.mission,t.location))
''')

    def test_support_reentrancy_and_failure_never_mark_an_unrelated_generation_supported(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
local t,path,token=select("afghanistan-normal")
local adds=0
assert(w.AppendSupport(token,function()
    adds=adds+1
    assert(not w.AppendSupport(token,function() adds=adds+1 end))
end))
assert(adds==1)
local t2,path2,token2=select("afghanistan-normal")
assert(not pcall(w.AppendSupport,token2,function() select("africa-normal") end))
assert(w.Status().pending_generation==0)
assert(not w.Configure(false))
assert(not pcall(w.FreezeAllocation,30010,10))
assert(not pcall(w.FreezeAllocation,30020,20))
assert(w.Status().cleanup_needed)
local done=w.CaptureTermination();assert(w.CompleteTermination(done))
local _,_,failed=select("afghanistan-normal")
assert(not pcall(w.AppendSupport,failed,function() error("partial engine add") end))
assert(not w.AppendSupport(failed,function() error("must not retry ambiguous add") end))
assert(not pcall(w.FreezeAllocation,30010,10))
''')

    def test_demo_and_sequence_do_not_open_acceptance_then_host_waits_for_live_peer(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal");clear()
demo=true;assert(not w.TryStart(token));assert(#calls==0)
demo=false;runtimeHook=function(p) p.sequence_name="Fixture_Demo" end
assert(not w.TryStart(token));assert(#calls==0)
runtimeHook=nil;local ready,why=w.TryStart(token)
assert(not ready and why=="waiting_for_live_peer")
assert(#calls==2 and calls[1]=="center" and calls[2]=="accept")
members,peerReady=2,true
ready,why=w.TryStart(token);assert(ready and why=="startup_calls_issued")
assert(calls[3]=="target")
assert(w.TryStart(token));assert(#calls==3)
peerReady=false;assert(not w.TryStart(token))
assert(w.Status().startup_blocked and w.Status().cleanup_needed)
assert(calls[4]=="block" and calls[5]=="stop")
''')

    def test_old_mission_teardown_does_not_release_a_failed_next_package_selection(self):
        self.run_lua(r'''
assert(w.Configure(true,provider));allocated("afghanistan-normal")
local nextTarget,_,nextToken=select("africa-normal")
assert(not pcall(w.AppendSupport,nextToken,function() select("afghanistan-recover-volgin") end))
main.OnTerminate({})
assert(w.Status().active_generation==0 and not w.Configure(false))
assert(not pcall(w.FreezeAllocation,nextTarget.mission,nextTarget.location))
assert(w.Status().active_generation==nextToken and w.Status().cleanup_needed)
main.OnTerminate({})
assert(w.Status().active_generation==0 and w.Configure(false))
''')

    def test_client_requires_preallocation_and_current_connection_without_creating_one(self):
        self.run_lua(r'''
role="client";members,peerReady=2,true
assert(w.Configure(true,provider))
local t,token=prepared("africa-normal");clear()
runtimeHook=function(p) p.connected=false end
assert(not w.TryStart(token));assert(#calls==0)
runtimeHook=nil;assert(w.TryStart(token))
assert(calls[1]=="center" and calls[2]=="accept" and calls[3]=="target")
''')

    def test_suspend_retries_failed_native_requests_and_retains_teardown_obligation(self):
        self.run_lua(r'''
members,peerReady=2,true;assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal");assert(w.TryStart(token));clear()
blockHook=function() error("cannot disable acceptance") end
stopHook=function() return false end
w.SuspendForReload()
assert(w.Status().cleanup_needed and w.Status().cooperative)
assert(w.Status().accepting_requested and w.Status().targeting_requested)
assert(w.Status().reason=="suspend_retry_needed")
blockHook,stopHook=nil,nil
w.SuspendForReload()
assert(not w.Status().accepting_requested and not w.Status().targeting_requested)
assert(main.IsCoop(30010) and not w.TryStart(token))
''')

    def test_runtime_identity_nonce_sample_and_realized_players_gate_start(self):
        mutations = (
            "p.nonce=p.nonce-1", "p.epoch=p.epoch+1", "p.sample_id=math.huge",
            "p.session_token=string.rep('f',64)", "p.role='client'", "p.local_player_realized=false",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.run_lua(r'''
members,peerReady=2,true;assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal");clear()
runtimeHook=function(p) MUTATION end
assert(not w.TryStart(token));assert(#calls==0)
'''.replace("MUTATION", mutation))
        for mutation in ("p.remote_player_realized=false", "p.players_realized=1"):
            with self.subTest(realization=mutation):
                self.run_lua(r'''
members,peerReady=2,true;assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal");clear()
runtimeHook=function(p) MUTATION end
assert(not w.TryStart(token));assert(not has("target"))
runtimeHook=nil;assert(w.TryStart(token));assert(has("target"))
'''.replace("MUTATION", mutation))

    def test_actual_reload_suspends_before_sequence_and_preserves_allocated_cleanup(self):
        self.run_lua(r'''
members,peerReady=2,true;assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal");assert(w.TryStart(token));clear()
local epoch=w.Status().epoch
mvars={};Tpp._requireList={"WWFreeRoam"}
TppCheckPoint={RegisterCheckPointList=function() record("checkpoints") end}
main.SetUpdateFunction=function() record("updates") end
main.SetMessageFunction=function() record("messages") end
main.OnReload({sequence={OnLoad=function()
    record("reload-sequence")
    assert(w.Status().startup_blocked and main.IsCoop(30010))
end}})
local expected={"block","stop","reload-sequence","checkpoints","updates","messages"}
assert(#calls==#expected);for i,v in ipairs(expected) do assert(calls[i]==v) end
assert(w.Status().epoch==epoch+1 and w.Status().cleanup_needed)
assert(not w.TryStart(token))
''')

    def test_actual_preparation_observes_only_after_original_engine_work(self):
        self.run_lua(r'''
assert(w.Configure(true,provider));allocated("afghanistan-normal")
assert(w.ObserveInitialized(30010,10));clear();mvars={}
TppMission={IsMissionStart=function() return false end,OnMissionStart=function() record("mission") end}
TppLocation={ActivateBlock=function() record("activate") end,IsMiddleAfrica=function() return false end}
TppWeather={OnMissionCanStart=function() record("weather") end}
TppMarker={OnMissionCanStart=function() record("markers") end}
TppResult={OnMissionCanStart=function() record("result") end}
TppQuest={InitializeQuestLoad=function() record("quests") end}
TppRatBird={OnMissionCanStart=function() record("animals") end}
TppLandingZone={OnMissionCanStart=function() record("landing") end}
TppOutOfMissionRangeEffect={Disable=function() record("range") end}
MotherBaseConstructConnector={}
Dynamite.AcceptMarkerRequests=function()
    assert(w.Status().phase=="initialized");record("accept-markers")
end
main.OnMissionCanStart()
assert(w.Status().phase=="prepared" and calls[#calls]=="accept-markers")
assert(#calls==10 and not has("accept") and not has("target"))
''')

    def test_native_reentrant_invalidation_and_partial_failure_never_report_success(self):
        for action in ("accept", "target", "throw_after_target"):
            with self.subTest(action=action):
                hook = {"accept":"acceptHook=function() w.SuspendForReload() end",
                        "target":"targetHook=function() w.SuspendForReload() end",
                        "throw_after_target":"targetHook=function() error('partial native target start') end"}[action]
                self.run_lua(r'''
members,peerReady=2,true;assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal");clear()
''' + hook + r'''
assert(not w.TryStart(token))
assert(w.Status().startup_blocked and w.Status().cleanup_needed)
assert(not w.Status().accepting_requested and not w.Status().targeting_requested)
assert(has("block"))
''')

    def test_allocation_hook_freezes_before_first_marker_and_coop_check(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
selected("afghanistan-normal")
TppWeather={OnEndMissionPrepareFunction=function() record("allocation-boundary");error("fixture stop after prefix") end}
local ok=pcall(main.OnAllocate,{})
assert(not ok and calls[#calls-1]=="ignore-markers" and calls[#calls]=="allocation-boundary")
assert(main.IsCoop(30010))
''')

    def test_termination_keeps_next_selection_and_cleans_after_callback_even_when_vars_change(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
local t,token=prepared("afghanistan-normal")
local nextTarget,nextToken=selected("africa-normal");clear()
main.OnTerminate({sequence={OnTerminate=function()
    record("sequence");vars.missionCode,vars.locationCode=30020,20;online=false
end}})
local expected={"sequence","stop","reset-online","disconnect","close","reset-client"}
assert(#calls==#expected);for i,v in ipairs(expected) do assert(calls[i]==v) end
assert(w.Status().active_generation==0 and w.Status().pending_generation==nextToken)
assert(w.FreezeAllocation(nextTarget.mission,nextTarget.location))
''')

    def test_termination_rethrows_false_nil_and_string_errors_after_owned_cleanup(self):
        for value in ("false", "nil", '"fixture callback error"'):
            with self.subTest(error=value):
                self.run_lua(r'''
assert(w.Configure(true,provider));prepared("afghanistan-normal");clear()
local expectedError=ERROR_VALUE
local ok,failure=pcall(main.OnTerminate,{sequence={OnTerminate=function() record("sequence");error(expectedError,0) end}})
assert(not ok and failure==expectedError)
assert(calls[1]=="sequence" and calls[#calls]=="reset-client")
assert(w.Status().active_generation==0)
'''.replace("ERROR_VALUE", value))

    def test_owned_teardown_attempts_every_step_and_retains_obligation_until_retry_succeeds(self):
        operations = {
            "Dynamite.StopNearestEnemyThread": "stop",
            "TppGameStatus.Reset": "reset-online",
            "TppNetworkUtil.SessionDisconnectPreparingMembers": "disconnect",
            "TppNetworkUtil.CloseSession": "close",
            "Dynamite.ResetClientSessionState": "reset-client",
        }
        for operation, call in operations.items():
            for failure in ("return false", "error('fixture cleanup failure')"):
                with self.subTest(operation=operation, failure=failure):
                    self.run_lua(r'''
assert(w.Configure(true,provider));prepared("afghanistan-normal");clear()
local original=OPERATION
OPERATION=function() record(CALL); FAILURE end
local callbacks=0
local scripts={sequence={OnTerminate=function() callbacks=callbacks+1;record("sequence") end}}
assert(not pcall(main.OnTerminate,scripts))
assert(w.Status().cleanup_needed and w.Status().active_generation~=0)
local expected={"sequence","stop","reset-online","disconnect","close","reset-client"}
assert(#calls==#expected);for i,v in ipairs(expected) do assert(calls[i]==v) end
OPERATION=original;clear();main.OnTerminate(scripts)
assert(callbacks==1 and #calls==5 and calls[#calls]=="reset-client")
assert(w.Status().active_generation==0)
'''.replace("OPERATION", operation).replace("CALL", json.dumps(call)).replace("FAILURE", failure))

    def test_common_game_start_records_demo_after_original_work_without_starting_network(self):
        self.run_lua(r'''
assert(w.Configure(true,provider));local t,token=allocated("afghanistan-normal")
assert(w.ObserveInitialized(30010,10));assert(w.ObservePrepared(30010,10));clear()
TppClock={Start=function() record("clock") end};gvars={ini_isTitleMode=true}
TppQuest={InitializeQuestActiveStatus=function() record("quests") end}
mvars={seq_demoSequneceList={[1]=true},seq_missionStartSequence=1}
main.EnableGameStatusForDemo=function() record("demo") end
main.EnableGameStatus=function() error("enabled playable status during demo") end
Player={};TppTerminal={OnMissionGameStart=function() record("terminal") end}
TppSequence={IsLandContinue=function() return false end}
TppSoundDaemon={ResetMute=function() record("sound") end}
main.OnMissionGameStart({})
assert(w.Status().phase=="game_started")
assert(#calls==5 and calls[1]=="clock" and calls[2]=="quests" and calls[3]=="demo" and calls[5]=="sound")
assert(not has("accept") and not has("target"))
''')

    def test_package_loader_default_trace_matches_upstream_for_all_branches_and_callback_arguments(self):
        original = subprocess.check_output(["git", "show", BASE + ":moddata/standalone/TppMissionList.lua"], cwd=SOURCE, text=True)
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "TppMissionList.lua"
            baseline.write_text(original)
            extra = r'''
TppDefine={LOCATION_ID={},MISSION_COMMON_PACK={ORDER_BOX="order-box"}}
for i,name in ipairs({"INIT","AFGH","MAFR","CYPR","GNTN","OMBS","MTBS","HLSP","MBQF","FLYK","SAND_AFGH","SAND_MAFR","SAND_MTBS"}) do TppDefine.LOCATION_ID[name]=i end
TppDefine.LOCATION_ID.AFGH,TppDefine.LOCATION_ID.MAFR=10,20
local branch,callbackArg=false,0
TppPackList={SetUseDdEmblemFova=function(v) record("emblem:"..v) end,
    AddLocationCommonScriptPack=function(v) record("scripts:"..tostring(v)) end,
    AddLocationCommonMissionAreaPack=function(v) record("area:"..tostring(v)) end,
    AddMissionPack=function(v) record("pack:"..v) end,
    IsMissionPackLabel=function(v) assert(v=="recoverVolginDemo");record("label");return branch end,
    MakeMissionPackList=function(m,fn) fn(callbackArg);return {} end}
local baseline=assert(loadfile(BASELINE_PATH))()
local current=assert(loadfile(CURRENT_PATH))()
for _,choice in ipairs({{30010,false},{30010,true},{30020,false}}) do
    for _,arg in ipairs({1,10,30010,"sentinel"}) do
        callbackArg,branch=arg,choice[2]
        WWFreeRoam=nil;clear();baseline.GetMissionPackagePath(choice[1])
        local expected=calls
        WWFreeRoam=w;clear();current.GetMissionPackagePath(choice[1])
        assert(#calls==#expected);for i,v in ipairs(expected) do assert(calls[i]==v) end
        assert(vars.missionCode==30010 and vars.locationCode==10)
    end
end
'''.replace("BASELINE_PATH", json.dumps(str(baseline))).replace("CURRENT_PATH", json.dumps(str(LIB / "TppMissionList.lua")))
            self.run_lua(extra)

    def test_actual_package_loader_routes_each_verified_branch_to_distinct_staged_assets(self):
        self.run_lua(r'''
assert(w.Configure(true,provider))
TppDefine={LOCATION_ID={},MISSION_COMMON_PACK={ORDER_BOX="order-box"}}
for i,name in ipairs({"INIT","AFGH","MAFR","CYPR","GNTN","OMBS","MTBS","HLSP","MBQF","FLYK","SAND_AFGH","SAND_MAFR","SAND_MTBS"}) do TppDefine.LOCATION_ID[name]=i end
TppDefine.LOCATION_ID.AFGH,TppDefine.LOCATION_ID.MAFR=10,20
local branch=false
TppPackList={SetUseDdEmblemFova=function() end,AddLocationCommonScriptPack=function() end,
    AddLocationCommonMissionAreaPack=function() end,
    AddMissionPack=function(v) record(v) end,
    IsMissionPackLabel=function(v) assert(v=="recoverVolginDemo");return branch end,
    MakeMissionPackList=function(m,fn) fn("callback-is-not-a-mission-id");return {} end}
local list=assert(loadfile(LIST_PATH))()
local seen={}
for _,t in ipairs(manifest.targets) do
    branch=t.branch=="recoverVolginDemo";clear()
    list.GetMissionPackagePath(t.mission)
    assert(has(t.staged_fpk) and has(manifest.support_fpk) and not has(t.source_fpk))
    local supportCount=0;for _,path in ipairs(calls) do if path==manifest.support_fpk then supportCount=supportCount+1 end end
    assert(supportCount==1 and not seen[t.staged_fpk]);seen[t.staged_fpk]=true
    assert(vars.missionCode==30010 and vars.locationCode==10)
    assert(w.FreezeAllocation(t.mission,t.location))
    local token=w.CaptureTermination(t.mission,t.location);assert(w.CompleteTermination(token))
end
'''.replace("LIST_PATH", json.dumps(str(LIB / "TppMissionList.lua"))))


if __name__ == "__main__":
    unittest.main()
