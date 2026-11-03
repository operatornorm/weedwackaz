"""Exercise the actual passive native/Lua readers; no engine execution is claimed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_dynamite_initial_sync import method
from test_dynamite_lifecycle import Lua

SOURCE = Path(os.environ.get("DYNAMITE_SOURCE_DIR", str(Path(__file__).resolve().parents[2] / "dynamite")))
INCLUDE = SOURCE / "hook/src"
OBSERVER = SOURCE / "moddata/standalone/WWRuntimeObservation.lua"


class NativeObservationTests(unittest.TestCase):
    def execute_native(self, mutation=None):
        header=(INCLUDE / "CoopRuntimeObservation.h").read_text()
        if mutation: header=mutation(header)
        binding_source=(INCLUDE / "DynamiteLua.cpp").read_text()
        self.assertEqual(binding_source.count('{"ReadRuntimeObservation", l_ReadRuntimeObservation}'),1)
        binding=method(binding_source,"int l_ReadRuntimeObservation(lua_State *L)")
        fixture=Path(__file__).with_name("dynamite_runtime_observation.cpp").read_text().replace("__NATIVE_BINDING__",binding)
        defaults="\n".join(method(binding_source,signature) for signature in (
            "int l_RuntimeObservationDue(lua_State *L)","int l_PublishRuntimeObservation(lua_State *L)","int l_StopRuntimeObservation(lua_State *L)","int l_ReadSteamInviteBinding(lua_State *L)"))
        fixture=fixture.replace("__DEFAULT_BRIDGE_BINDINGS__",defaults)
        with tempfile.TemporaryDirectory(prefix="ww-native-observation-") as directory:
            root=Path(directory)
            (root / "CoopRuntimeObservation.h").write_text(header)
            (root / "fixture.cpp").write_text(fixture)
            binary=root / "observation-test"
            result=subprocess.run([os.environ.get("CXX","g++"),"-std=c++23","-Wall","-Wextra","-Werror","-pedantic","-pthread",
                "-I",str(root),"-I",str(INCLUDE),str(root / "fixture.cpp"),str(INCLUDE / "SteamInviteProbe.cpp"),"-Wl,-l:liblua5.1.so.0","-o",str(binary)],
                text=True,capture_output=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            return subprocess.run([str(binary)],text=True,capture_output=True,timeout=15)

    def test_actual_native_binding_and_tracker_with_real_lua(self):
        result=self.execute_native()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("PASS:",result.stdout)

    def test_unknown_membership_cannot_become_solo_mutation(self):
        before='return {"main_session_unavailable", std::nullopt};'
        def mutate(value):
            self.assertEqual(value.count(before),1)
            return value.replace(before,'return {"main_session_unavailable", 1};')
        result=self.execute_native(mutate)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("unavailable count must be omitted",result.stderr)

    def test_native_liveness_overclaim_mutation_is_caught(self):
        before='field("peer_liveness_verified", false);'
        def mutate(value):
            self.assertEqual(value.count(before),1)
            return value.replace(before,'field("peer_liveness_verified", true);')
        result=self.execute_native(mutate)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("unverified peer liveness must stay false",result.stderr)


class LuaObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.lua=Lua()

    def run_lua(self,code):
        self.lua.execute("local observer=assert(loadfile("+json.dumps(str(OBSERVER))+"))()\n"+code)

    def test_missing_apis_are_unknown_without_side_effects_or_automatic_dispatch(self):
        self.run_lua(r'''
assert(observer.Init==nil and observer.OnReload==nil and observer.OnMessage==nil and observer.Update==nil)
local s=observer.Snapshot()
assert(s.schema==1 and s.observation_only and not s.can_authorize and not s.coherent_snapshot_verified)
assert(s.native.status=="unavailable" and next(s.context)==nil and next(s.player_slots)==nil)
for _,v in pairs(s.verification) do assert(v==false) end
''')

    def test_known_getters_report_observations_without_promoting_members_or_slots(self):
        self.run_lua(r'''
vars={missionCode=30010,locationCode=10,playerPosX=0,playerPosY=0,playerPosZ=0}
TppSequence={GetCurrentSequenceName=function() return "Seq_Fixture_Free" end,GetCurrentSequenceIndex=function() return 4 end,
    IsMissionPrepareFinished=function() return true end}
TppDemo={IsNotPlayable=function() return false end}
TppCoder={GetWorldCenter=function() return {GetX=function() return 10 end,GetY=function() return 20 end,GetZ=function() return 30 end} end}
PlayerInfo={GetLocalPlayerIndex=function() return 0 end}
local slots={}
GameObject={NULL_ID=65535,GetGameObjectIdByIndex=function(kind,slot) assert(kind=="TppPlayer2");slots[#slots+1]=slot;return slot end}
Dynamite={ReadRuntimeObservation=function() return {schema=1,observation_only=true,can_authorize=false,native_available=true,
    configured_role="host",sample_id="18446744073709551615",initial_vars_generation="17",initial_vars_required=4,
    initial_vars_applied=4,initial_vars_handlers_complete=true,session_connected_bookkeeping=true,
    member_query_status="native_count_observed",engine_member_count=2,peer_liveness_verified=true,secret="do not copy"} end}
local s=observer.Snapshot()
assert(s.native.engine_member_count==2 and s.native.sample_id=="18446744073709551615")
assert(s.native.peer_liveness_verified==nil and s.native.secret==nil)
assert(s.context.sequence_name=="Seq_Fixture_Free" and s.context.sequence_index==4 and s.context.prepare_finished and s.context.not_playable==false)
assert(s.context.world_center.z==30 and s.context.local_position.x==0 and s.context.local_player_index==0)
assert(#slots==2 and slots[1]==0 and slots[2]==1 and s.player_slots.slot0_present and s.player_slots.slot1_present)
assert(not s.can_authorize);for _,v in pairs(s.verification) do assert(v==false) end
''')

    def test_api_lookup_errors_and_malformed_returns_stay_unknown(self):
        self.run_lua(r'''
TppSequence=setmetatable({},{__index=function() error("half initialized") end})
TppDemo={IsNotPlayable=function() error("no context") end}
GameObject=setmetatable({},{__index=function() error("NULL_ID not initialized") end})
Dynamite={ReadRuntimeObservation=function() return {schema=1,observation_only=true,can_authorize=true} end}
vars={missionCode=0/0,locationCode=-1,playerPosX=math.huge,playerPosY=0,playerPosZ=0}
local s=observer.Snapshot()
assert(s.native.status=="unavailable" and next(s.context)==nil and next(s.player_slots)==nil and not s.can_authorize)
''')

    def test_stale_bookkeeping_and_unknown_query_never_supply_member_count(self):
        self.run_lua(r'''
Dynamite={ReadRuntimeObservation=function() return {schema=1,observation_only=true,can_authorize=false,
    session_connected_bookkeeping=true,member_query_status="main_session_unavailable",engine_member_count=2,
    initial_vars_generation="123",sample_id="1"} end}
vars={missionCode=30010,locationCode=10}
local a=observer.Snapshot()
vars.missionCode,vars.locationCode=30020,20
local b=observer.Snapshot()
assert(a.context.mission==30010 and b.context.mission==30020 and b.context.location==20)
assert(b.native.session_connected_bookkeeping and b.native.engine_member_count==nil)
assert(not b.verification.peer_liveness and not b.can_authorize)
''')

    def test_bad_vectors_identifiers_and_missing_null_sentinel_do_not_probe(self):
        self.run_lua(r'''
TppCoder={GetWorldCenter=function() return {GetX=function() return 0/0 end,GetY=function() return 20 end,GetZ=function() return 30 end} end}
TppSequence={GetCurrentSequenceName=function() return "/private/path" end,GetCurrentSequenceIndex=function() return math.huge end}
PlayerInfo={GetLocalPlayerIndex=function() return 15 end}
GameObject={GetGameObjectIdByIndex=function() error("must not probe without verified NULL_ID") end}
local s=observer.Snapshot()
assert(next(s.context)==nil and next(s.player_slots)==nil)
GameObject.NULL_ID=65535
GameObject.GetGameObjectIdByIndex=function(_,slot) if slot==0 then return 65535 else return -1 end end
local b=observer.Snapshot();assert(b.player_slots.slot0_present==false and b.player_slots.slot1_present==nil)
''')


if __name__=="__main__": unittest.main()
