// Local fixture: fixed synthetic DLL, no Steam/MGSV paths, registry or network.
#include "SteamInviteBindings.h"
#include <windows.h>
#include <filesystem>
#include <cstring>
#include <memory>

using namespace Dynamite::Invites;
constexpr std::uint64_t Self=0x0110000100000001ULL, Friend=0x0110000100000002ULL;
int main() {
    wchar_t executable[32768];const auto length=GetModuleFileNameW(nullptr,executable,32768);
    if(!length || length==32768) return 3;
    const auto directory=std::filesystem::path(executable).parent_path();
    const auto output=directory/L"ww-invite-abi-result.json";
    // Preserve existing results. Only files next to this test executable are used.
    const auto report=CreateFileW(output.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(report==INVALID_HANDLE_VALUE) return 4;
    const auto dll=LoadLibraryExW((directory/L"ww-invite-fake.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    const char *failure="fixture_dll_unavailable";
    bool success=false;
    bool retainModule=false;
    if(dll) {
        const auto marker=reinterpret_cast<const char*(*)()>(GetProcAddress(dll,"WWFake_Marker"));
        const auto setApp=reinterpret_cast<void(*)(std::uint32_t)>(GetProcAddress(dll,"WWFake_SetAppId"));
        const auto deliver=reinterpret_cast<int(*)(const char*)>(GetProcAddress(dll,"WWFake_Deliver"));
        if(marker && setApp && deliver && !std::strcmp(marker(),"ww-mgsv-invite-fixture-1")) {
            // The literal fingerprint here is an explicit fixture injection. The
            // real loaded-module probe independently hashes the real Steam DLL.
            const auto api=Resolve(SteamDllSha,[dll](const char *name){return GetProcAddress(dll,name);});
            Context context;
            failure="flat_binding_failed";
            if(api && Bind(*api,context)==BindStatus::Bound) {
                setApp(480);Context rejected;
                failure="wrong_app_guard_failed";
                if(Bind(*api,rejected)==BindStatus::WrongApp) {
                    setApp(AppId);auto callback=std::make_unique<CallbackQueue>();Channel channel(context,*callback);
                    failure="callback_registration_failed";
                    if(channel.StartObserving()) {
                        const Intent intent{Friend,"afghanistan-normal",std::string(32,'a'),1,1200};
                        const auto text=Encode(intent);
                        failure="cross_dll_callback_failed";
                        success=deliver(text.c_str())==1 && channel.Poll(1000) && channel.TakeIntent(1000)==intent;
                        if(!channel.Stop()) { success=false;failure="callback_unregister_failed"; }
                    }
                    // A failed unregister must retain callback storage and code
                    // until process exit; never free a registered callback.
                    if(callback->Registered()) { retainModule=true;callback.release(); }
                }
            }
        } else failure="fixture_marker_missing";
    }
    // No game/Steam identities, machine paths or diagnostic payloads in the report.
    const std::string json=std::string("{\"schema\":1,\"kind\":\"ww_invite_windows_fixture\",\"result\":\"")+(success?"PASS":"FAIL")+
        "\",\"reason\":\""+(success?"synthetic_cross_dll_binding_and_callback":failure)+
        "\",\"real_steam_used\":false,\"game_launched\":false,\"co_op_verified\":false}\n";
    DWORD written=0;const bool recorded=WriteFile(report,json.data(),static_cast<DWORD>(json.size()),&written,nullptr) && written==json.size();
    CloseHandle(report);
    if(dll && !retainModule) FreeLibrary(dll);
    return !recorded?5:success?0:2;
}
