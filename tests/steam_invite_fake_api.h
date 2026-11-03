#pragma once
#include "SteamInviteBindings.h"
#include <cstring>
#include <string>
#ifdef _WIN32
#define WW_FAKE_EXPORT extern "C" __declspec(dllexport)
#else
#define WW_FAKE_EXPORT extern "C"
#endif

namespace Fixture {
    using namespace Dynamite::Invites;
    inline constexpr std::uint64_t Self = 0x0110000100000001ULL, Friend = 0x0110000100000002ULL;
    inline int clientObject, friendObject, utilsObject, userObject;
    inline bool ready = true, friendsReady = true, userReady = true, registeredAck = true, callbackOnUnregister = false;
    inline bool unregisterAck = true;
    inline std::uint32_t app = AppId;
    inline int relation = 3, sends = 0, registrations = 0, unregistrations = 0, calls = 0;
    inline CallbackBase *registered = nullptr;
    inline std::string payload;
    inline void SetFlags(CallbackBase *callback, unsigned char value, int id) {
        // Simulate the independently verified SDK's documented flags/id writes.
        std::memcpy(reinterpret_cast<unsigned char *>(callback)+8,&value,1);
        std::memcpy(reinterpret_cast<unsigned char *>(callback)+12,&id,4);
    }
    inline RichJoin Event(std::uint64_t inviter, const std::string &text) {
        RichJoin event{}; event.inviter.value=inviter;
        std::memcpy(event.connect,text.data(),std::min(text.size(),sizeof event.connect)); return event;
    }
}
WW_FAKE_EXPORT void *SteamClient() { ++Fixture::calls; return Fixture::ready ? &Fixture::clientObject : nullptr; }
WW_FAKE_EXPORT std::int32_t SteamAPI_GetHSteamUser() { ++Fixture::calls; return Fixture::ready ? 1 : 0; }
WW_FAKE_EXPORT std::int32_t SteamAPI_GetHSteamPipe() { ++Fixture::calls; return Fixture::ready ? 1 : 0; }
WW_FAKE_EXPORT void *SteamAPI_ISteamClient_GetISteamFriends(std::intptr_t self,std::int32_t user,std::int32_t pipe,const char *version) {
    ++Fixture::calls;
    return self==reinterpret_cast<std::intptr_t>(&Fixture::clientObject) && user==1 && pipe==1 && !std::strcmp(version,"SteamFriends015") && Fixture::friendsReady ? &Fixture::friendObject : nullptr;
}
WW_FAKE_EXPORT void *SteamAPI_ISteamClient_GetISteamUser(std::intptr_t self,std::int32_t user,std::int32_t pipe,const char *version) {
    ++Fixture::calls;
    return self==reinterpret_cast<std::intptr_t>(&Fixture::clientObject) && user==1 && pipe==1 && !std::strcmp(version,"SteamUser018") && Fixture::userReady ? &Fixture::userObject : nullptr;
}
WW_FAKE_EXPORT void *SteamAPI_ISteamClient_GetISteamUtils(std::intptr_t self,std::int32_t pipe,const char *version) {
    ++Fixture::calls;
    return self==reinterpret_cast<std::intptr_t>(&Fixture::clientObject) && pipe==1 && !std::strcmp(version,"SteamUtils007") ? &Fixture::utilsObject : nullptr;
}
WW_FAKE_EXPORT std::uint32_t SteamAPI_ISteamUtils_GetAppID(std::intptr_t) { ++Fixture::calls; return Fixture::app; }
WW_FAKE_EXPORT std::uint64_t SteamAPI_ISteamUser_GetSteamID(std::intptr_t) { ++Fixture::calls; return Fixture::Self; }
WW_FAKE_EXPORT int SteamAPI_ISteamFriends_GetFriendRelationship(std::intptr_t,Dynamite::Invites::SteamId) { ++Fixture::calls; return Fixture::relation; }
WW_FAKE_EXPORT bool SteamAPI_ISteamFriends_InviteUserToGame(std::intptr_t,Dynamite::Invites::SteamId,const char *payload) {
    ++Fixture::calls; ++Fixture::sends; Fixture::payload=payload; return true;
}
WW_FAKE_EXPORT void SteamAPI_RegisterCallback(Dynamite::Invites::CallbackBase *callback,int id) {
    ++Fixture::calls; ++Fixture::registrations;
    if (id==337 && callback->GetCallbackSizeBytes()==264 && callback->LayoutMatches() && Fixture::registeredAck) {
        Fixture::SetFlags(callback,1,id); Fixture::registered=callback;
    }
}
WW_FAKE_EXPORT void SteamAPI_UnregisterCallback(Dynamite::Invites::CallbackBase *callback) {
    ++Fixture::calls; ++Fixture::unregistrations;
    if (Fixture::callbackOnUnregister) {
        auto event=Fixture::Event(Fixture::Friend,Fixture::payload);callback->Run(&event);
    }
    if (Fixture::unregisterAck) { Fixture::SetFlags(callback,0,337); Fixture::registered=nullptr; }
}
#undef WW_FAKE_EXPORT
