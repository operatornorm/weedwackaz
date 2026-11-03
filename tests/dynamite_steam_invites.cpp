#include "steam_invite_fake_api.h"
#include "SteamInviteProbe.h"
#include <iostream>
#include <cstdlib>
#include <map>
#include <type_traits>

using namespace Dynamite::Invites;
void check(bool v,const char *message) { if(!v) {std::cerr<<message<<'\n';std::exit(1);} }
using Proc=void(*)();
std::map<std::string,Proc> symbols={
    {"SteamClient",reinterpret_cast<Proc>(&SteamClient)},
    {"SteamAPI_GetHSteamUser",reinterpret_cast<Proc>(&SteamAPI_GetHSteamUser)},
    {"SteamAPI_GetHSteamPipe",reinterpret_cast<Proc>(&SteamAPI_GetHSteamPipe)},
    {"SteamAPI_ISteamClient_GetISteamFriends",reinterpret_cast<Proc>(&SteamAPI_ISteamClient_GetISteamFriends)},
    {"SteamAPI_ISteamClient_GetISteamUser",reinterpret_cast<Proc>(&SteamAPI_ISteamClient_GetISteamUser)},
    {"SteamAPI_ISteamClient_GetISteamUtils",reinterpret_cast<Proc>(&SteamAPI_ISteamClient_GetISteamUtils)},
    {"SteamAPI_ISteamUtils_GetAppID",reinterpret_cast<Proc>(&SteamAPI_ISteamUtils_GetAppID)},
    {"SteamAPI_ISteamUser_GetSteamID",reinterpret_cast<Proc>(&SteamAPI_ISteamUser_GetSteamID)},
    {"SteamAPI_ISteamFriends_GetFriendRelationship",reinterpret_cast<Proc>(&SteamAPI_ISteamFriends_GetFriendRelationship)},
    {"SteamAPI_ISteamFriends_InviteUserToGame",reinterpret_cast<Proc>(&SteamAPI_ISteamFriends_InviteUserToGame)},
    {"SteamAPI_RegisterCallback",reinterpret_cast<Proc>(&SteamAPI_RegisterCallback)},
    {"SteamAPI_UnregisterCallback",reinterpret_cast<Proc>(&SteamAPI_UnregisterCallback)},
};
Intent intent(std::uint64_t host=Fixture::Friend) { return {host,"afghanistan-normal",std::string(32,'a'),1,1200}; }
int main() {
    check(ProbeLoadedSteamInvites()==ProbeStatus::Disabled,"production probe default performs no Steam calls");
    check(Fixture::calls==0,"default cannot access SDK");
    const auto payload=Encode(intent());check(payload.size()<256,"Steam payload fits callback array");
    check(Parse(payload,1000)==intent(),"canonical payload roundtrip");
    for (const auto &bad : {std::string{},std::string("+connect mgo"),payload+":extra",payload+";quit",std::string(256,'x')}) check(!Parse(bad,1000),"malformed/foreign payload rejected");
    check(!Parse(payload,1200) && !Parse(payload,899),"expired or excessive lifetime rejected");
    auto wrong=intent();wrong.epoch=0;check(!Parse(Encode(wrong),1000),"zero epoch rejected");
    wrong=intent();wrong.target="story-unverified";check(!Parse(Encode(wrong),1000),"unverified target rejected");
    wrong=intent();wrong.session=std::string(32,'0');check(!Parse(Encode(wrong),1000),"empty session rejected");
    auto otherBuild=payload;otherBuild[otherBuild.find(std::string(ExeSha))]='0';check(!Parse(otherBuild,1000),"wrong executable rejected");
    auto overflow=payload;const auto tail=overflow.rfind(":1:");overflow.replace(tail+1,1,"4294967296");check(!Parse(overflow,1000),"epoch overflow rejected");
    std::array<std::string_view,3> args{"mgsvtpp.exe","-steam",payload};
    check(ColdIntent(args,1000)==intent(),"cold launch is data-only");
    args[0]=payload;check(!ColdIntent(args,1000),"duplicate cold intent rejected");
    int resolutions=0;
    auto get=[&](const char *name){++resolutions;auto at=symbols.find(name);return at==symbols.end()?nullptr:at->second;};
    check(!Resolve("wrong-dll-hash",get) && resolutions==0,"untrusted module rejected before symbol access");
    for (const auto &[missing,_] : symbols) {
        (void)_;
        check(!Resolve(SteamDllSha,[&](const char *name){return missing==name?nullptr:get(name);}),"each missing flat export blocks binding");
    }
    check(Fixture::calls==0,"export resolution never calls SDK");
    const auto api=Resolve(SteamDllSha,get);check(api.has_value(),"complete flat exports resolve");Context context;
    Fixture::ready=false;check(Bind(*api,context)==BindStatus::ContextNotReady && !context.OnOwner(),"unready context clears old state");
    Fixture::ready=true;Fixture::app=480;check(Bind(*api,context)==BindStatus::WrongApp,"wrong runtime AppID rejected");
    Fixture::app=AppId;Fixture::friendsReady=false;check(Bind(*api,context)==BindStatus::ContextNotReady,"null versioned interface rejected");
    Fixture::friendsReady=true;check(Bind(*api,context)==BindStatus::Bound,"verified flat interface versions bind");
    static_assert(!std::is_copy_constructible_v<Channel> && !std::is_move_constructible_v<Channel>);
    CallbackQueue callback;check(callback.LayoutMatches() && callback.GetCallbackSizeBytes()==264,"official AMD64 callback contract");
    Channel channel(context,callback);check(channel.StartObserving(),"single callback registration");
    check(!channel.StartObserving() && Fixture::registrations==1,"no duplicate callback registration");
    check(!channel.Send(Fixture::Friend,intent(Fixture::Self),{},1000) && Fixture::sends==0,"missing native activation proofs never send");
    ActivationProof proof{true,true,true,true};
    for (int flag=0;flag<4;++flag) {
        auto partial=proof;
        if(flag==0)partial.saveIsolation=false;
        if(flag==1)partial.resourceContract=false;
        if(flag==2)partial.peerProtocol=false;
        if(flag==3)partial.mgoRouting=false;
        check(!channel.Send(Fixture::Friend,intent(Fixture::Self),partial,1000),"every missing contract blocks Steam write");
    }
    Fixture::relation=1;check(!channel.Send(Fixture::Friend,intent(Fixture::Self),proof,1000),"nonfriend invite denied");
    Fixture::relation=3;check(channel.Send(Fixture::Friend,intent(Fixture::Self),proof,1000) && Fixture::sends==1,"explicit fixture-authorized send");
    check(!channel.Send(Fixture::Friend,intent(Fixture::Self),proof,1000) && Fixture::sends==1,"send attempt deduplicated");
    bool foreign=true;std::thread worker([&]{foreign=channel.Send(Fixture::Friend,intent(Fixture::Self),proof,1000);});worker.join();
    check(!foreign && Fixture::sends==1,"foreign thread cannot call outgoing SDK");
    foreign=true;std::thread statusThread([&]{foreign=channel.Active();});statusThread.join();check(!foreign,"foreign status reader cannot access mutable channel state");
    auto event=Fixture::Event(Fixture::Friend,payload);
    const auto calls=Fixture::calls;
    std::thread callbackThread([&]{callback.Run(&event);});callbackThread.join();
    check(Fixture::calls==calls,"callback thread only copies data");
    foreign=true;std::thread pollThread([&]{foreign=channel.Poll(1000);});pollThread.join();check(!foreign,"foreign thread cannot drain");
    check(channel.Poll(1000) && channel.TakeIntent(1000)==intent(),"frame receives owned join intent only");
    callback.Run(&event);check(!channel.Poll(1000),"accepted invitation deduplicated");
    auto renewed=intent();renewed.expires=1250;event=Fixture::Event(Fixture::Friend,Encode(renewed));callback.Run(&event);
    check(channel.Poll(1000) && channel.TakeIntent(1000)==renewed,"explicitly renewed invitation may retry same hosted session");
    auto foreignInvite=Fixture::Event(Fixture::Friend,"+connect mgo");callback.Run(&foreignInvite);check(!channel.Poll(1000),"ordinary game invitations ignored without reset");
    std::memset(event.connect,'a',sizeof event.connect);callback.Run(&event);check(!channel.Poll(1000),"unterminated SDK-sized data rejected");
    event=Fixture::Event(Fixture::Friend,payload);callback.Run(&event,true,0);check(!channel.Poll(1000),"IO failure callback ignored");
    callback.Disable();check(callback.EnableNext().has_value(),"fresh callback generation");for(int i=0;i<20;++i)callback.Run(&event);
    check(callback.Drain().size()==8,"callback queue has bounded capacity");
    Fixture::callbackOnUnregister=true;Fixture::payload=payload;
    Fixture::unregisterAck=false;
    check(!channel.Stop() && !channel.Active(),"failed unregister retains cleanup but suspends actions");
    check(!channel.Send(Fixture::Friend,intent(Fixture::Self),proof,1000) && Fixture::sends==1,"unregister failure cannot revive sends");
    Fixture::unregisterAck=true;
    check(channel.Stop() && channel.Stop() && Fixture::unregistrations==2,"stop retries and remains idempotent with callback during unregister");
    callback.Run(&event);check(callback.Drain().empty(),"post-stop callback storage remains safe and disabled");
    check(channel.StartObserving(),"restart receives new local generation");
    event=Fixture::Event(Fixture::Self,payload);callback.Run(&event);check(!channel.Poll(1000),"SDK inviter must match payload host");
    event=Fixture::Event(Fixture::Friend,payload);callback.Run(&event);check(!channel.Poll(1200),"stale queued invitation expires");
    check(channel.Stop(),"explicit teardown before callback storage destruction");
    const auto oldGeneration=callback.EnableNext();callback.Disable();
    const auto newGeneration=callback.EnableNext();callback.Disable();
    check(oldGeneration && newGeneration && *newGeneration>*oldGeneration,"callback storage never reuses a local generation");
    std::cout<<"PASS: production flat binder, strict protocol, callback ABI/queue and gated invitation channel\n";
}
