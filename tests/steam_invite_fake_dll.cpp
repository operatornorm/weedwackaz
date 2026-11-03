// Synthetic fixture only. This is never named/recommended as steam_api64.dll.
#include "steam_invite_fake_api.h"
#ifdef _WIN32
#define WW_EXPORT extern "C" __declspec(dllexport)
#else
#define WW_EXPORT extern "C"
#endif
WW_EXPORT const char *WWFake_Marker() { return "ww-mgsv-invite-fixture-1"; }
WW_EXPORT void WWFake_SetAppId(std::uint32_t value) { Fixture::app=value; }
WW_EXPORT int WWFake_Deliver(const char *text) {
    if(!Fixture::registered || !text) return 0;
    auto event=Fixture::Event(Fixture::Friend,text);Fixture::registered->Run(&event);return 1;
}
