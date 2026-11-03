#include "steam_invite_fake_api.h"
#include "RuntimeCheck.h"
#include <cstdlib>
#include <iostream>
using namespace Dynamite::Invites;
void check(bool value,const char *text) { if(!value) { std::cerr<<text<<'\n';std::exit(1); } }
int initializations=0,shutdowns=0;
bool initialize() { ++initializations; return Fixture::ready; }
void shutdown() { ++shutdowns; }
Api api{SteamClient,SteamAPI_GetHSteamUser,SteamAPI_GetHSteamPipe,SteamAPI_ISteamClient_GetISteamFriends,SteamAPI_ISteamClient_GetISteamUser,
    SteamAPI_ISteamClient_GetISteamUtils,SteamAPI_ISteamUtils_GetAppID,SteamAPI_ISteamUser_GetSteamID,SteamAPI_ISteamFriends_GetFriendRelationship,
    SteamAPI_ISteamFriends_InviteUserToGame,SteamAPI_RegisterCallback,SteamAPI_UnregisterCallback};
int main() {
    CallbackQueue callback;
    auto result=WWRuntimeCheck::Run(false,initialize,shutdown,api,callback);
    check(!result.steamAttempted && initializations==0 && Fixture::calls==0,"untrusted module cannot initialize SDK");
    result=WWRuntimeCheck::Run(true,nullptr,shutdown,api,callback);
    check(!result.steamAttempted && initializations==0,"missing initialization export cannot initialize SDK");
    Fixture::ready=false; result=WWRuntimeCheck::Run(true,initialize,shutdown,api,callback);
    check(!result.initialized && initializations==1 && shutdowns==0 && Fixture::calls==0,"failed init cannot use SDK or claim ownership");
    Fixture::ready=true; Fixture::app=480; result=WWRuntimeCheck::Run(true,initialize,shutdown,api,callback);
    check(!result.bound && std::string(result.status)=="wrong_app_id" && Fixture::registrations==0 && shutdowns==1,"wrong app refuses registration but closes owned context");
    Fixture::app=AppId; result=WWRuntimeCheck::Run(true,initialize,shutdown,api,callback);
    check(result.Passed() && shutdowns==2 && Fixture::registrations==1 && Fixture::unregistrations==1,"real pipeline binds registers unregisters and closes owned SDK context");
    check(Fixture::sends==0 && !callback.Registered(),"no invitations or leaked registration");
    const auto json=WWRuntimeCheck::Json(result);
    check(json.find("\"real_callback_delivery_verified\":false")!=std::string::npos && json.find("\"co_op_verified\":false")!=std::string::npos,"registration cannot claim delivery or co-op");
    check(json.find(std::to_string(Fixture::Self))==std::string::npos && json.find(std::string(ExeSha))==std::string::npos,"report has no identities or game paths/data");
    Fixture::registeredAck=false; result=WWRuntimeCheck::Run(true,initialize,shutdown,api,callback);
    check(!result.Passed() && result.detached && result.shutdown && !callback.Registered(),"failed registration cleans up owned context");
    Fixture::registeredAck=true; Fixture::unregisterAck=false;
    const auto stopped=shutdowns; result=WWRuntimeCheck::Run(true,initialize,shutdown,api,callback);
    check(!result.Passed() && result.registered && !result.detached && !result.shutdown && shutdowns==stopped && callback.Registered(),"failed unregister retains callback and module context until exit");
    Fixture::unregisterAck=true; SteamAPI_UnregisterCallback(&callback); shutdown();
    check(!callback.Registered(),"fixture releases simulated failure before stack storage destruction");
    std::cout<<"PASS: standalone Steam runtime checker with fake API; no real Steam or game\n";
}
