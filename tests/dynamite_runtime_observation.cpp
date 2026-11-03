// Host fixture executes the actual exported binding against the real Lua5.1 VM.
#include "CoopRuntimeObservation.h"
#include "DynamiteSyncImpl/InitialVarSync.h"
#include "SteamInviteProbe.h"
#include <cstdlib>
#include <iostream>
#include <set>
#include <thread>
#include <vector>

extern "C" {
    struct lua_State;
    using lua_Integer = std::ptrdiff_t;
    using lua_CFunction = int (*)(lua_State *);
    lua_State *luaL_newstate();
    void luaL_openlibs(lua_State *);
    void lua_close(lua_State *);
    int luaL_loadstring(lua_State *, const char *);
    int lua_pcall(lua_State *, int, int, int);
    int lua_gettop(lua_State *);
    void lua_settop(lua_State *, int);
    void lua_createtable(lua_State *, int, int);
    void lua_pushboolean(lua_State *, int);
    void lua_pushinteger(lua_State *, lua_Integer);
    void lua_pushstring(lua_State *, const char *);
    void lua_pushcclosure(lua_State *, lua_CFunction, int);
    void lua_setfield(lua_State *, int, const char *);
    const char *lua_tolstring(lua_State *, int, std::size_t *);
}

void require(bool value, const char *message) {
    if (!value) { std::cerr << message << '\n'; std::exit(1); }
}
int mainCalls=0, countCalls=0, rawCount=0;
alignas(16) char sessionStorage[64]{};
void *mainSession=nullptr;
void *sessionGetter() { ++mainCalls; return mainSession; }
int countGetter(void *value) {
    ++countCalls;
    require(value==sessionStorage+0x20,"existing SessionImpl2 offset must be preserved");
    return rawCount;
}
auto *FoxNtSessionGetMainSession = &sessionGetter;
auto *GetSessionMemberCount = &countGetter;

namespace Dynamite {
    struct StubCore {
        bool created=false, host=false, connected=false;
        bool GetSessionCreated() const { return created; }
        bool GetHostSessionCreated() const { return host; }
        bool GetSessionConnected() const { return connected; }
    };
    struct StubSync {
        InitialVarSync tracker;
        auto ObserveInitialVariables() const { return tracker.Inspect(); }
    };
    struct StubHook {
        struct { bool Host=true; } cfg;
        StubCore dynamiteCore;
        StubSync dynamiteSyncImpl;
    };
    StubHook *g_hook=nullptr;
__NATIVE_BINDING__
__DEFAULT_BRIDGE_BINDINGS__
}

void checkLua(lua_State *L, const char *code) {
    const auto top=lua_gettop(L);
    require(luaL_loadstring(L,code)==0,"fixture Lua must compile");
    if (lua_pcall(L,0,0,0)!=0) {
        std::cerr << lua_tolstring(L,-1,nullptr) << '\n'; std::exit(1);
    }
    require(lua_gettop(L)==top,"native observation must preserve caller stack");
}

int main() {
    auto *L=luaL_newstate();require(L!=nullptr,"Lua VM allocation");luaL_openlibs(L);
    lua_pushcclosure(L,Dynamite::l_ReadRuntimeObservation,0);
    lua_setfield(L,-10002,"snapshot");
    lua_pushcclosure(L,Dynamite::l_RuntimeObservationDue,0);lua_setfield(L,-10002,"disabledDue");
    lua_pushcclosure(L,Dynamite::l_PublishRuntimeObservation,0);lua_setfield(L,-10002,"disabledPublish");
    lua_pushcclosure(L,Dynamite::l_StopRuntimeObservation,0);lua_setfield(L,-10002,"disabledStop");
    lua_pushcclosure(L,Dynamite::l_ReadSteamInviteBinding,0);lua_setfield(L,-10002,"disabledSteamProbe");
    // A sentinel remains underneath every compile/call and native result table.
    lua_pushinteger(L,731);
    checkLua(L,R"(
        assert(disabledDue()==false and disabledPublish('anything')==false and disabledStop()==nil)
        local steam=disabledSteamProbe()
        assert(steam.schema==1 and steam.status=='disabled' and steam.can_authorize==false and steam.callbacks_registered==false and steam.invites_sent==false)
        local s=snapshot();assert(s.schema==1 and s.observation_only and s.can_authorize==false)
        assert(s.native_available==false and s.configured_role=='unknown')
        assert(s.member_query_status=='unavailable' and s.engine_member_count==nil,'unavailable count must be omitted')
        assert(type(s.sample_id)=='string' and not s.initial_vars_handlers_complete)
        assert(s.peer_liveness_verified==false,'unverified peer liveness must stay false')
    )");
    Dynamite::StubHook hook;Dynamite::g_hook=&hook;
    checkLua(L,"local s=snapshot();assert(s.member_query_status=='mod_session_not_created' and s.engine_member_count==nil,'unavailable count must be omitted')");
    require(mainCalls==0 && countCalls==0,"uncreated session must not query native state");
    hook.dynamiteCore.host=true;
    FoxNtSessionGetMainSession=nullptr;
    checkLua(L,"local s=snapshot();assert(s.member_query_status=='native_api_unavailable' and s.engine_member_count==nil,'unavailable count must be omitted')");
    FoxNtSessionGetMainSession=&sessionGetter;
    checkLua(L,"local s=snapshot();assert(s.member_query_status=='main_session_unavailable' and s.engine_member_count==nil,'unavailable count must be omitted')");
    mainSession=sessionStorage;
    for (int count : {-1,0,1,2,16,17}) {
        rawCount=count;
        checkLua(L, count<0 || count>16
            ? "local s=snapshot();assert(s.member_query_status=='native_count_out_of_range' and s.engine_member_count==nil,'unavailable count must be omitted')"
            : ("local s=snapshot();assert(s.member_query_status=='native_count_observed' and s.engine_member_count=="+std::to_string(count)+");assert(not s.peer_liveness_verified,'unverified peer liveness must stay false')").c_str());
    }
    const std::vector<std::string> required{"a","b","c","d"};
    hook.dynamiteSyncImpl.tracker.Begin(required);
    auto token=hook.dynamiteSyncImpl.tracker.Generation();
    for (const auto &name : required) hook.dynamiteSyncImpl.tracker.Record(token,"svars",name,true);
    checkLua(L,"local s=snapshot();assert(s.initial_vars_required==4 and s.initial_vars_applied==4 and s.initial_vars_handlers_complete);assert(s.initial_vars_complete_arrays_verified==false)");
    hook.dynamiteSyncImpl.tracker.Reset();
    hook.dynamiteCore.connected=true;mainSession=nullptr;
    checkLua(L,R"(
        local a,b=snapshot(),snapshot()
        assert(a.session_connected_bookkeeping and a.engine_member_count==nil,'cached connection must not fabricate membership')
        assert(a.initial_vars_required==0 and a.initial_vars_applied==0 and not a.initial_vars_handlers_complete)
        assert(a.initial_vars_generation~='0' and a.sample_id~=b.sample_id)
        assert(not a.coherent_snapshot_verified and not a.remote_player_realization_verified)
    )");
    // The production counter cannot wrap into an old sample identity.
    Dynamite::ObservationCounter endCounter(std::numeric_limits<std::uint64_t>::max()-1);
    require(endCounter.Next()==std::numeric_limits<std::uint64_t>::max(),"last sample ID must be exact");
    require(!endCounter.Next() && !endCounter.Next(),"exhausted sample counter must not wrap");
    Dynamite::ObservationCounter concurrent;
    std::mutex mu;std::set<std::uint64_t> samples;
    std::vector<std::thread> workers;
    for (int i=0;i<4;++i) workers.emplace_back([&] {
        for(int j=0;j<100;++j) { auto next=concurrent.Next();std::lock_guard lock(mu);require(next && samples.insert(*next).second,"samples must be unique under contention"); }
    });
    for(auto &worker:workers) worker.join();
    require(samples.size()==400,"all concurrent samples collected");
    lua_close(L);
    std::cout << "PASS: actual native binding, Lua stack, unknown states, counters and tracker snapshot\n";
}
