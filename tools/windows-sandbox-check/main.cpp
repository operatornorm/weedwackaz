// Standalone, no Steam/game/installer/account code. Uses an ALREADY installed
// Windows Sandbox. The guest tests only this harness's newly created folders.
#include "Plan.h"
#include <winsock2.h>
#include <windows.h>
#include <iphlpapi.h>
#include <bcrypt.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <shellapi.h>
#include <tlhelp32.h>
#include <filesystem>
#include <cstring>
#include <vector>

using namespace WWSandbox;
namespace {
    struct File {
        HANDLE value=INVALID_HANDLE_VALUE;
        void Close(){if(value!=INVALID_HANDLE_VALUE){CloseHandle(value);value=INVALID_HANDLE_VALUE;}}
        ~File(){Close();}
        File()=default;File(const File&)=delete;File& operator=(const File&)=delete;
    };
    struct Hash {
        BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
        std::vector<unsigned char> storage;
        ~Hash(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}
    };
    template<class T> struct Com {T *value=nullptr;~Com(){if(value)value->Release();}};
    bool Equal(const wchar_t *a,const wchar_t *b){return CompareStringOrdinal(a,-1,b,-1,TRUE)==CSTR_EQUAL;}
    bool Regular(HANDLE file){
        BY_HANDLE_FILE_INFORMATION info{};
        return GetFileType(file)==FILE_TYPE_DISK && GetFileInformationByHandle(file,&info)
            && !(info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT));
    }
    std::optional<Digest> Fingerprint(HANDLE file){
        LARGE_INTEGER size{};
        if(!Regular(file)||!GetFileSizeEx(file,&size)||size.QuadPart<=0||size.QuadPart>8*1024*1024)return {};
        Hash h;
        if(BCryptOpenAlgorithmProvider(&h.algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return {};
        DWORD bytes=0,received=0;
        if(BCryptGetProperty(h.algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&bytes),sizeof bytes,&received,0)<0
            ||received!=sizeof bytes||!bytes||bytes>65536)return {};
        h.storage.resize(bytes);
        if(BCryptCreateHash(h.algorithm,&h.hash,h.storage.data(),bytes,nullptr,0,0)<0)return {};
        std::array<unsigned char,16384> buffer{};std::uint64_t total=0;
        for(;;){DWORD count=0;if(!ReadFile(file,buffer.data(),buffer.size(),&count,nullptr))return {};if(!count)break;
            total+=count;if(total>static_cast<std::uint64_t>(size.QuadPart)||BCryptHashData(h.hash,buffer.data(),count,0)<0)return {};}
        Digest result{};
        if(total!=static_cast<std::uint64_t>(size.QuadPart)||BCryptFinishHash(h.hash,result.data(),result.size(),0)<0)return {};
        return result;
    }
    bool NewDirectory(const std::filesystem::path &path){
        if(!CreateDirectoryW(path.c_str(),nullptr))return false;
        const auto flags=GetFileAttributesW(path.c_str());
        return flags!=INVALID_FILE_ATTRIBUTES && (flags&FILE_ATTRIBUTE_DIRECTORY) && !(flags&FILE_ATTRIBUTE_REPARSE_POINT);
    }
    bool WriteNew(const std::filesystem::path &path,const void *data,DWORD size){
        File file;file.value=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file.value==INVALID_HANDLE_VALUE)return false;
        DWORD count=0;return WriteFile(file.value,data,size,&count,nullptr)&&count==size&&FlushFileBuffers(file.value);
    }
    bool OwnWriteProbe(const std::filesystem::path &path){
        File file;file.value=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file.value==INVALID_HANDLE_VALUE)return false;
        file.Close();return DeleteFileW(path.c_str()); // Only the new empty file we created.
    }
    void InspectNetwork(GuestPacket &packet){
        ULONG bytes=0;
        auto status=GetAdaptersAddresses(AF_UNSPEC,GAA_FLAG_SKIP_DNS_SERVER|GAA_FLAG_SKIP_MULTICAST|GAA_FLAG_SKIP_ANYCAST,nullptr,nullptr,&bytes);
        if(status==ERROR_NO_DATA){packet.flags|=AdaptersInspected|NoUpNonLoopback;return;}
        if(status!=ERROR_BUFFER_OVERFLOW||!bytes||bytes>1024*1024)return;
        std::vector<unsigned char> buffer(bytes);
        auto *adapters=reinterpret_cast<IP_ADAPTER_ADDRESSES*>(buffer.data());
        status=GetAdaptersAddresses(AF_UNSPEC,GAA_FLAG_SKIP_DNS_SERVER|GAA_FLAG_SKIP_MULTICAST|GAA_FLAG_SKIP_ANYCAST,nullptr,adapters,&bytes);
        if(status!=NO_ERROR)return;
        packet.flags|=AdaptersInspected;
        bool active=false;
        for(const auto *adapter=adapters;adapter;adapter=adapter->Next)
            if(adapter->IfType!=IF_TYPE_SOFTWARE_LOOPBACK && adapter->OperStatus==IfOperStatusUp)active=true;
        if(!active)packet.flags|=NoUpNonLoopback;
        // No address, MAC, adapter name, DNS data or network request is exported.
    }
    void InspectGraphics(GuestPacket &packet){
        Com<ID3D11Device> device;Com<ID3D11DeviceContext> context;
        const D3D_FEATURE_LEVEL requested=D3D_FEATURE_LEVEL_11_0;D3D_FEATURE_LEVEL level{};
        auto hr=D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,&requested,1,D3D11_SDK_VERSION,&device.value,&level,&context.value);
        packet.hresult=static_cast<std::uint32_t>(hr);
        if(FAILED(hr)||!device.value||!context.value||level!=requested)return;
        packet.featureLevel=level;
        Com<IDXGIDevice> dxgi;Com<IDXGIAdapter> adapter;Com<IDXGIAdapter1> versioned;
        hr=device.value->QueryInterface(__uuidof(IDXGIDevice),reinterpret_cast<void**>(&dxgi.value));
        if(SUCCEEDED(hr)&&dxgi.value)hr=dxgi.value->GetAdapter(&adapter.value);
        else if(SUCCEEDED(hr))hr=E_FAIL;
        if(SUCCEEDED(hr)&&adapter.value)hr=adapter.value->QueryInterface(__uuidof(IDXGIAdapter1),reinterpret_cast<void**>(&versioned.value));
        DXGI_ADAPTER_DESC1 description{};
        if(SUCCEEDED(hr)&&versioned.value)hr=versioned.value->GetDesc1(&description);
        else if(SUCCEEDED(hr))hr=E_FAIL;
        packet.hresult=static_cast<std::uint32_t>(hr);
        if(SUCCEEDED(hr)&&!(description.Flags&DXGI_ADAPTER_FLAG_SOFTWARE))packet.flags|=HardwareD3D11;
        // Never export the adapter description, identifiers or VRAM details.
    }
    int Guest(const std::filesystem::path &executable,const Nonce &nonce){
        wchar_t user[257]{};DWORD count=257;
        const bool expectedUser=GetUserNameW(user,&count)&&Equal(user,L"WDAGUtilityAccount");
        const bool expectedPath=Equal(executable.c_str(),L"C:\\MGSVQA\\Input\\ww-sandbox-check.exe");
        // Accidental-host-execution guards, NOT VM attestation. No writes or GPU
        // calls precede both guards. There is no environment-variable override.
        if(!expectedUser||!expectedPath)return 20;
        GuestPacket packet;packet.nonce=nonce;packet.flags=UserGuard|PathGuard;
        File self;self.value=CreateFileW(executable.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        const auto digest=Fingerprint(self.value);if(!digest)return 21;packet.helper=*digest;
        const auto run=Hex(nonce);const std::wstring wide(run.begin(),run.end());
        File denied;
        const auto sentinel=std::filesystem::path(L"C:\\MGSVQA\\Input")/(L"input-write-probe-"+wide);
        denied.value=CreateFileW(sentinel.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(denied.value==INVALID_HANDLE_VALUE){if(GetLastError()==ERROR_ACCESS_DENIED)packet.flags|=InputDenied;}
        else{denied.Close();DeleteFileW(sentinel.c_str());}
        const auto output=std::filesystem::path(L"C:\\MGSVQA\\Output");
        if(OwnWriteProbe(output/(L"output-write-probe-"+wide)))packet.flags|=OutputWritable;
        const auto scratch=std::filesystem::path(L"C:\\MGSVQA")/(L"Scratch-"+wide);
        if(NewDirectory(scratch)&&OwnWriteProbe(scratch/L"empty-write-probe"))packet.flags|=ScratchWritable;
        InspectNetwork(packet);InspectGraphics(packet);
        const auto temporary=output/(L"probe-"+wide+L".tmp");
        const auto target=output/(L"probe-"+wide+L".bin");
        if(!WriteNew(temporary,&packet,sizeof packet)||!MoveFileExW(temporary.c_str(),target.c_str(),MOVEFILE_WRITE_THROUGH))return 22;
        return Passed(packet,nonce,*digest)?0:2;
    }
    bool NoExistingSandbox(){
        File snapshot;snapshot.value=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);
        if(snapshot.value==INVALID_HANDLE_VALUE)return false;
        PROCESSENTRY32W process{};process.dwSize=sizeof process;
        if(!Process32FirstW(snapshot.value,&process))return false;
        do{if(Equal(process.szExeFile,L"WindowsSandbox.exe")||Equal(process.szExeFile,L"WindowsSandboxClient.exe")
            ||Equal(process.szExeFile,L"WindowsSandboxRemoteSession.exe"))return false;}while(Process32NextW(snapshot.value,&process));
        return GetLastError()==ERROR_NO_MORE_FILES;
    }
    struct Summary {
        const char *result="BLOCKED",*status="preflight_not_complete";
        Nonce nonce{};Digest helper{};GuestPacket packet{};
        bool launcherFound=false,memory=false,noExisting=false,launched=false,received=false,valid=false;
    };
    std::string Json(const Summary &s){
        const auto b=[](bool value){return value?"true":"false";};
        const auto flag=[&](Flag bit){return s.valid&&(s.packet.flags&bit)!=0;};
        return std::string("{\"schema\":1,\"kind\":\"ww_windows_sandbox_check\",\"result\":\"")+s.result+"\",\"status\":\""+s.status+
            "\",\"run_id\":\""+Hex(s.nonce)+"\",\"helper_sha256\":\""+Hex(s.helper)+
            "\",\"sandbox_launcher_found\":"+b(s.launcherFound)+",\"host_memory_preflight_passed\":"+b(s.memory)+
            ",\"no_existing_sandbox_observed\":"+b(s.noExisting)+",\"launch_requested\":"+b(s.launched)+
            ",\"guest_report_received\":"+b(s.received)+",\"guest_report_valid\":"+b(s.valid)+
            ",\"expected_guest_user_observed\":"+b(flag(UserGuard))+",\"expected_guest_path_observed\":"+b(flag(PathGuard))+
            ",\"input_create_access_denied\":"+b(flag(InputDenied))+",\"output_write_delete_succeeded\":"+b(flag(OutputWritable))+
            ",\"guest_scratch_write_delete_succeeded\":"+b(flag(ScratchWritable))+",\"adapter_query_succeeded\":"+b(flag(AdaptersInspected))+
            ",\"no_up_nonloopback_adapter_observed\":"+b(flag(NoUpNonLoopback))+",\"hardware_D3D11_feature_11_0_observed\":"+b(flag(HardwareD3D11))+
            ",\"d3d_hresult\":"+std::to_string(s.valid?s.packet.hresult:0)+
            ",\"networking_requested\":\"disabled\",\"VM_attestation_verified\":false,\"all_network_isolation_verified\":false,\"save_isolation_verified\":false,\"game_started\":false,\"Steam_started\":false,\"co_op_verified\":false}\n";
    }
    void HostRun(const std::filesystem::path &executable,Summary &s){
        if(BCryptGenRandom(nullptr,s.nonce.data(),s.nonce.size(),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0||!ParseNonce(Hex(s.nonce))){s.status="nonce_generation_failed";return;}
        wchar_t system[32768];const auto length=GetSystemDirectoryW(system,32768);
        if(!length||length>=32768){s.status="system_directory_unavailable";return;}
        const auto launcher=std::filesystem::path(system)/L"WindowsSandbox.exe";
        const auto attributes=GetFileAttributesW(launcher.c_str());
        s.launcherFound=attributes!=INVALID_FILE_ATTRIBUTES&&!(attributes&FILE_ATTRIBUTE_DIRECTORY);
        if(!s.launcherFound){s.status="sandbox_feature_unavailable";return;}
        s.noExisting=NoExistingSandbox();
        if(!s.noExisting){s.status="existing_sandbox_or_process_query_unavailable";return;}
        ULONGLONG installedKB=0;MEMORYSTATUSEX memory{};memory.dwLength=sizeof memory;
        s.memory=GetPhysicallyInstalledSystemMemory(&installedKB)&&installedKB>=8ULL*1024*1024&&GlobalMemoryStatusEx(&memory)&&memory.ullAvailPhys>=5ULL*1024*1024*1024;
        if(!s.memory){s.status="harness_memory_preflight_not_met";return;}
        const auto run=Hex(s.nonce);const std::wstring wide(run.begin(),run.end());
        const auto base=executable.parent_path()/(L"ww-sandbox-run-"+wide),input=base/L"Input",output=base/L"Output";
        if(!NewDirectory(base)||!NewDirectory(input)||!NewDirectory(output)){s.status="exclusive_workspace_creation_failed";return;}
        File self;self.value=CreateFileW(executable.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        const auto digest=Fingerprint(self.value);
        if(!digest){s.status="helper_fingerprint_failed";return;}s.helper=*digest;
        const auto staged=input/L"ww-sandbox-check.exe";
        if(!CopyFileW(executable.c_str(),staged.c_str(),TRUE)){s.status="helper_staging_failed";return;}
        File pinned;pinned.value=CreateFileW(staged.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        const auto stagedHash=Fingerprint(pinned.value);
        if(!stagedHash||*stagedHash!=s.helper){s.status="staged_helper_fingerprint_failed";return;}
        const auto config=Configuration(input.wstring(),output.wstring(),s.nonce);
        const auto filename=base/L"check.wsb";
        if(!config){s.status="invalid_local_workspace_path";return;}
        const auto xml=std::wstring(1,static_cast<wchar_t>(0xfeff))+*config;
        if(!WriteNew(filename,xml.data(),static_cast<DWORD>(xml.size()*sizeof(wchar_t)))){s.status="configuration_creation_failed";return;}
        auto command=L"\""+launcher.wstring()+L"\" \""+filename.wstring()+L"\"";
        std::vector<wchar_t> mutableCommand(command.begin(),command.end());mutableCommand.push_back(0);
        STARTUPINFOW startup{};startup.cb=sizeof startup;PROCESS_INFORMATION process{};
        if(!CreateProcessW(launcher.c_str(),mutableCommand.data(),nullptr,nullptr,FALSE,0,nullptr,base.c_str(),&startup,&process)){
            s.status="sandbox_launch_failed";return;}
        CloseHandle(process.hThread);CloseHandle(process.hProcess);s.launched=true;
        const auto result=output/(L"probe-"+wide+L".bin");
        const auto start=GetTickCount64();
        while(GetTickCount64()-start<180000){
            File file;file.value=CreateFileW(result.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
            if(file.value!=INVALID_HANDLE_VALUE){
                s.received=true;LARGE_INTEGER size{};DWORD count=0;
                if(Regular(file.value)&&GetFileSizeEx(file.value,&size)&&size.QuadPart==sizeof(GuestPacket)
                    &&ReadFile(file.value,&s.packet,sizeof s.packet,&count,nullptr)&&count==sizeof s.packet)
                    s.valid=Valid(s.packet,s.nonce,s.helper);
                s.result=s.valid&&Passed(s.packet,s.nonce,s.helper)?"PASS":"FAIL";
                s.status=!s.valid?"guest_report_rejected":(Passed(s.packet,s.nonce,s.helper)?"harness_observations_passed":"guest_observations_failed");return;
            }
            const auto error=GetLastError();
            if(error!=ERROR_FILE_NOT_FOUND&&error!=ERROR_PATH_NOT_FOUND&&error!=ERROR_SHARING_VIOLATION){s.result="FAIL";s.status="guest_report_open_failed";return;}
            Sleep(250);
        }
        s.result="TIMEOUT";s.status="no_matching_guest_report_within_180_seconds";
        // Never kill, reconfigure, or take over any Sandbox session.
    }
}
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int){
    wchar_t path[32768];const auto length=GetModuleFileNameW(nullptr,path,32768);if(!length||length>=32768)return 3;
    const std::filesystem::path executable(path);
    int argc=0;auto **argv=CommandLineToArgvW(GetCommandLineW(),&argc);if(!argv)return 3;
    if(argc==3&&Equal(argv[1],L"--guest")){
        const std::wstring value(argv[2]);LocalFree(argv);
        if(value.size()!=32||std::any_of(value.begin(),value.end(),[](wchar_t c){return c>127;}))return 20;
        const auto nonce=ParseNonce(std::string(value.begin(),value.end()));
        return nonce?Guest(executable,*nonce):20;
    }
    LocalFree(argv);if(argc!=1)return 3;
    const auto directory=executable.parent_path();
    for(const auto *name:{L"mgsvtpp.exe",L"steam.exe",L"steam_api64.dll",L"dinput8.dll"}){
        if(GetFileAttributesW((directory/name).c_str())!=INVALID_FILE_ATTRIBUTES){
            MessageBoxW(nullptr,L"Extract this check to a new folder outside Steam and game folders.",L"MGSV Sandbox prerequisite check",MB_OK|MB_ICONERROR);return 4;}
    }
    File report;report.value=CreateFileW((directory/L"ww-sandbox-result.json").c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(report.value==INVALID_HANDLE_VALUE){MessageBoxW(nullptr,L"Use a fresh writable extraction folder. Existing results are never overwritten.",L"MGSV Sandbox prerequisite check",MB_OK|MB_ICONERROR);return 4;}
    Summary summary;
    try{HostRun(executable,summary);}catch(...){summary.result="FAIL";summary.status="helper_exception";}
    const auto json=Json(summary);DWORD count=0;
    const bool saved=WriteFile(report.value,json.data(),json.size(),&count,nullptr)&&count==json.size()&&FlushFileBuffers(report.value);
    report.Close();
    MessageBoxW(nullptr,saved?L"Send ww-sandbox-result.json from the helper folder, including BLOCKED/FAIL/TIMEOUT results. If Sandbox opened, close it when finished. No Steam or MGSV was started.":L"The result could not be saved.",L"MGSV Sandbox prerequisite check",MB_OK|(saved?MB_ICONINFORMATION:MB_ICONERROR));
    return !saved?5:std::string_view(summary.result)=="PASS"?0:2;
}
