#include "CoopStatusFile.h"
#include <cstdlib>
#include <iostream>
#ifndef _WIN32
#include <sys/stat.h>
#endif

using namespace Dynamite::QA;
void check(bool v,const char *message) { if(!v) {std::cerr<<message<<'\n';std::exit(1);} }
std::string read(const std::filesystem::path &p) {std::ifstream s(p,std::ios::binary);return {std::istreambuf_iterator<char>(s),{}};}
void request(const std::filesystem::path &dir,char id) {std::ofstream(dir/"request.txt")<<"WWQA1\n"<<std::string(32,id)<<"\n";}
std::string fixture() {
    auto v=Json::object();
    v.set("schema",1).set("observation_only",true).set("can_authorize",false).set("coherent_snapshot_verified",false);
    v.set("native",Json::object().set("status","unavailable")).set("context",Json::object()).set("player_slots",Json::object());
    auto proofs=Json::object();
    for(auto name:{"peer_liveness","player_realization","same_world","center_agreement","complete_initial_sync","protocol_epoch","playable_free_roam_contract","save_isolation"}) proofs.set(name,false);
    v.set("verification",proofs);return v.dump();
}
int main(int argc,char **argv) {
    check(argc==2,"fixture directory required");const std::filesystem::path dir=argv[1];
    std::filesystem::create_directories(dir);int lua=1,other=2;
    StatusFile bridge(dir);
    check(!bridge.Due(&lua,1000),"missing request stays disabled");
#ifndef _WIN32
    check(mkfifo((dir/"request.txt").c_str(),0600)==0,"FIFO fixture");
    check(!bridge.Due(&lua,1500),"FIFO request rejected without opening");
    std::filesystem::remove(dir/"request.txt");
#endif
    check(!std::filesystem::exists(dir/"status.json"),"disabled bridge writes nothing");
    request(dir,'a');check(bridge.Due(&lua,2000),"valid request arms caller");
    check(!bridge.Publish(&other,fixture(),2000),"wrong Lua context cannot publish");
    bool wrongThread=true;std::thread worker([&]{wrongThread=bridge.Publish(&lua,fixture(),2000);});worker.join();
    check(!wrongThread,"wrong thread cannot publish");
    check(bridge.Publish(&lua,fixture(),2000),"caller publishes atomically");
    const auto first=read(dir/"status.json");
    check(!bridge.Publish(&lua,fixture(),2001),"one publication per granted frame");
    check(!bridge.Due(&lua,2100),"rate bound prevents timer refresh");
    check(read(dir/"status.json")==first,"reads do not refresh publication");
    check(bridge.Due(&lua,2500),"next real update grants a publication");
    Json overclaim;std::string ignored;check(coopbridge::json::parse(fixture(),overclaim,ignored),"fixture JSON");
    overclaim.set("can_authorize",true);auto invalid=overclaim.dump();
    check(!bridge.Publish(&lua,invalid,2500),"overclaim must fail");
    check(bridge.Due(&lua,3000),"later update after invalid payload");
    request(dir,'b');check(!bridge.Publish(&lua,fixture(),3000),"changed request fences outstanding publication");
    check(bridge.Due(&lua,3500),"new run arms new generation");
    check(bridge.Publish(&lua,fixture(),3500),"new run publishes");
    Json status;std::string error;check(coopbridge::json::parse(read(dir/"status.json"),status,error),"published JSON parses");
    check(status.get("run_id").str()==std::string(32,'b') && status.get("generation").str()=="2" && status.get("frame_id").str()=="1","new run provenance resets frame only");
    bridge.Stop(&lua);bridge.Stop(&lua);check(!bridge.Due(&lua,4000),"repeated stop cannot release the stopped run");
    check(read(dir/"status.json")==status.dump()+"\n","stop does not fabricate new observations");
    request(dir,'c');check(bridge.Due(&lua,4500),"fresh run permitted");
    std::ofstream(dir/("status-"+std::string(32,'c')+".tmp"))<<"preserve";
    check(!bridge.Publish(&lua,fixture(),4500),"existing temp file never overwritten");
    check(read(dir/("status-"+std::string(32,'c')+".tmp"))=="preserve","exclusive output preserved");
    std::cout<<"PASS: actual status publisher, affinity, request generation, freshness and atomic file guards\n";
}
