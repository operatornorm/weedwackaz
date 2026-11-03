// Owner-approved standalone Windows check. No MGSV launch, injection, save API,
// friend enumeration, invitation sending, callback pumping, or install action.
#include "RuntimeCheck.h"
#include <windows.h>
#include <commdlg.h>
#include <bcrypt.h>
#include <filesystem>
#include <array>

using namespace Dynamite::Invites;
namespace {
    struct File {
        HANDLE value = INVALID_HANDLE_VALUE;
        ~File() { if (value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    };
    struct Hash {
        BCRYPT_ALG_HANDLE algorithm = nullptr;
        BCRYPT_HASH_HANDLE hash = nullptr;
        std::vector<unsigned char> object;
        ~Hash() { if (hash) BCryptDestroyHash(hash); if (algorithm) BCryptCloseAlgorithmProvider(algorithm,0); }
    };
    bool Fingerprint(HANDLE file) {
        LARGE_INTEGER size;
        if (!GetFileSizeEx(file,&size) || size.QuadPart != 211368) return false;
        Hash resources;
        if (BCryptOpenAlgorithmProvider(&resources.algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0) return false;
        DWORD length=0,received=0;
        if (BCryptGetProperty(resources.algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&length),sizeof length,&received,0)<0
            || received!=sizeof length || !length || length>65536) return false;
        resources.object.resize(length);
        if (BCryptCreateHash(resources.algorithm,&resources.hash,resources.object.data(),length,nullptr,0,0)<0) return false;
        std::array<unsigned char,16384> buffer;
        std::uint64_t total=0;
        for (;;) {
            DWORD count=0;
            if (!ReadFile(file,buffer.data(),buffer.size(),&count,nullptr)) return false;
            if (!count) break;
            total+=count;
            if (total>211368 || BCryptHashData(resources.hash,buffer.data(),count,0)<0) return false;
        }
        std::array<unsigned char,32> digest;
        if (total!=211368 || BCryptFinishHash(resources.hash,digest.data(),digest.size(),0)<0) return false;
        constexpr char hex[]="0123456789abcdef";
        std::string text;
        for (const auto byte:digest) { text+=hex[byte>>4]; text+=hex[byte&15]; }
        return text==SteamDllSha;
    }
    bool AppMarker(const std::filesystem::path &directory, File &marker) {
        marker.value=CreateFileW((directory/L"steam_appid.txt").c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if (marker.value==INVALID_HANDLE_VALUE) return false;
        LARGE_INTEGER size;
        if (!GetFileSizeEx(marker.value,&size) || size.QuadPart!=7) return false;
        std::array<char,7> text; DWORD count=0;
        return ReadFile(marker.value,text.data(),text.size(),&count,nullptr) && count==7
            && std::string_view(text.data(),text.size())=="287700\n";
    }
    bool AppEnvironment() {
        // Preserve the owner's environment; refuse another app selector instead
        // of overriding it or initializing the wrong account/app context first.
        for (const auto *name:{L"SteamAppId",L"SteamGameId"}) {
            wchar_t value[32]{};
            const auto count=GetEnvironmentVariableW(name,value,32);
            if (count>=32 || (count && std::wstring_view(value,count)!=L"287700")) return false;
        }
        return true;
    }
    bool EmptyTestLocation(const std::filesystem::path &directory) {
        for (const auto *name:{L"mgsvtpp.exe",L"steam.exe",L"steam_api64.dll",L"dinput8.dll"})
            if (GetFileAttributesW((directory/name).c_str())!=INVALID_FILE_ATTRIBUTES) return false;
        return true;
    }
}
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int) {
    wchar_t filename[32768]; const auto length=GetModuleFileNameW(nullptr,filename,32768);
    if (!length || length==32768) return 3;
    const auto directory=std::filesystem::path(filename).parent_path();
    File marker;
    if (!EmptyTestLocation(directory) || !AppMarker(directory,marker)) {
        MessageBoxW(nullptr,L"Extract the complete check into a NEW folder outside Steam and game folders. Keep the supplied steam_appid.txt unchanged.",L"MGSV Steam runtime check",MB_OK|MB_ICONERROR);
        return 4;
    }
    File report;
    report.value=CreateFileW((directory/L"ww-steam-runtime-result.json").c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (report.value==INVALID_HANDLE_VALUE) {
        MessageBoxW(nullptr,L"Cannot create a new result beside the helper. Use a fresh writable folder; existing results are never overwritten.",L"MGSV Steam runtime check",MB_OK|MB_ICONERROR);
        return 4;
    }
    WWRuntimeCheck::Result result;
    result.status="file_selection_cancelled";
    std::array<wchar_t,32768> selected{};
    OPENFILENAMEW chooser{};
    chooser.lStructSize=sizeof chooser; chooser.lpstrFile=selected.data(); chooser.nMaxFile=selected.size();
    chooser.lpstrTitle=L"Select steam_api64.dll from your MGSV co-op COPY (read only)";
    chooser.lpstrFilter=L"MGSV Steam DLL (steam_api64.dll)\0steam_api64.dll\0\0";
    chooser.Flags=OFN_FILEMUSTEXIST|OFN_PATHMUSTEXIST|OFN_NOCHANGEDIR|OFN_DONTADDTORECENT;
    File pinned;
    if (!AppEnvironment()) result.status="conflicting_Steam_app_environment";
    else if (GetOpenFileNameW(&chooser)) {
        // Deny replacement/writes while hashing AND loading the selected file.
        // No DLL code executes until the complete original pin matches.
        pinned.value=CreateFileW(selected.data(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_SEQUENTIAL_SCAN,nullptr);
        result.status="module_fingerprint_rejected";
        if (pinned.value!=INVALID_HANDLE_VALUE && Fingerprint(pinned.value)) {
            std::array<wchar_t,32768> finalPath{};
            const auto finalLength=GetFinalPathNameByHandleW(pinned.value,finalPath.data(),finalPath.size(),FILE_NAME_NORMALIZED|VOLUME_NAME_GUID);
            result.status="module_final_path_failed";
            if (finalLength && finalLength<finalPath.size() && SetCurrentDirectoryW(directory.c_str())) {
                result.status="module_load_failed";
                // Use the verified handle's resolved path. Dependencies may come
                // only from Windows, not other DLLs beside the owner's game.
                const auto module=LoadLibraryExW(finalPath.data(),nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
                if (module) {
                    const auto api=Resolve(SteamDllSha,[module](const char *name) { return GetProcAddress(module,name); });
                    result.status="missing_exports";
                    if (api) {
                        const auto initialize=reinterpret_cast<bool(*)()>(GetProcAddress(module,"SteamAPI_Init"));
                        const auto shutdown=reinterpret_cast<void(*)()>(GetProcAddress(module,"SteamAPI_Shutdown"));
                        // Deliberately retain module + callback until process
                        // exit even after unregister. No callback lifetime guess.
                        auto *callback=new CallbackQueue;
                        result=WWRuntimeCheck::Run(true,initialize,shutdown,*api,*callback);
                    }
                }
            }
        }
    }
    const auto json=WWRuntimeCheck::Json(result);
    DWORD count=0;
    if (!WriteFile(report.value,json.data(),json.size(),&count,nullptr) || count!=json.size() || !FlushFileBuffers(report.value)) {
        MessageBoxW(nullptr,L"The check could not save its result.",L"MGSV Steam runtime check",MB_OK|MB_ICONERROR); return 5;
    }
    MessageBoxW(nullptr,result.Passed()?L"Steam binding and callback registration passed. Send ww-steam-runtime-result.json from the helper folder. This does not verify invite delivery or co-op.":
        L"The check did not pass. Send ww-steam-runtime-result.json from the helper folder. No game was launched or invitation sent.",L"MGSV Steam runtime check",MB_OK|(result.Passed()?MB_ICONINFORMATION:MB_ICONWARNING));
    return result.Passed()?0:2;
}
