#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace WWSandbox {
    using Nonce = std::array<unsigned char,16>;
    using Digest = std::array<unsigned char,32>;
    inline std::string Hex(const auto &bytes) {
        constexpr char alphabet[]="0123456789abcdef";
        std::string result;
        for (const auto b:bytes) { result+=alphabet[b>>4];result+=alphabet[b&15]; }
        return result;
    }
    inline std::optional<Nonce> ParseNonce(std::string_view value) {
        if(value.size()!=32 || value.find_first_not_of("0123456789abcdef")!=value.npos || value.find_first_not_of('0')==value.npos) return {};
        Nonce result{};
        const auto digit=[](char c) { return c<='9'?c-'0':c-'a'+10; };
        for(std::size_t i=0;i<result.size();++i) result[i]=static_cast<unsigned char>((digit(value[i*2])<<4)|digit(value[i*2+1]));
        return result;
    }
    inline std::wstring Xml(std::wstring_view value) {
        std::wstring out;
        for(const auto c:value) {
            if(c==L'&')out+=L"&amp;";else if(c==L'<')out+=L"&lt;";else if(c==L'>')out+=L"&gt;";
            else if(c==L'\"')out+=L"&quot;";else if(c==L'\'')out+=L"&apos;";else out+=c;
        }
        return out;
    }
    inline bool LocalPath(std::wstring_view path) {
        return path.size()>3 && path.size()<30000 && ((path[0]>=L'A'&&path[0]<=L'Z') || (path[0]>=L'a'&&path[0]<=L'z'))
            && path[1]==L':' && path[2]==L'\\' && path.find_first_of(L"\r\n\t\"<>") == path.npos
            && std::none_of(path.begin(),path.end(),[](wchar_t c){return c<32;});
    }
    inline std::optional<std::wstring> Configuration(std::wstring_view input,std::wstring_view output,const Nonce &nonce) {
        if(!LocalPath(input) || !LocalPath(output) || input==output || !ParseNonce(Hex(nonce)))return {};
        const auto text=Hex(nonce);const std::wstring run(text.begin(),text.end());
        return L"<?xml version=\"1.0\" encoding=\"utf-16\"?>\r\n<Configuration>\r\n"
            L"<VGpu>Enable</VGpu><Networking>Disable</Networking>\r\n"
            L"<AudioInput>Disable</AudioInput><VideoInput>Disable</VideoInput>\r\n"
            L"<PrinterRedirection>Disable</PrinterRedirection><ClipboardRedirection>Disable</ClipboardRedirection>\r\n"
            L"<MemoryInMB>4096</MemoryInMB><MappedFolders>\r\n<MappedFolder><HostFolder>"+Xml(input)+
            L"</HostFolder><SandboxFolder>C:\\MGSVQA\\Input</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>\r\n"
            L"<MappedFolder><HostFolder>"+Xml(output)+
            L"</HostFolder><SandboxFolder>C:\\MGSVQA\\Output</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>\r\n"
            L"</MappedFolders><LogonCommand><Command>&quot;C:\\MGSVQA\\Input\\ww-sandbox-check.exe&quot; --guest "+run+
            L"</Command></LogonCommand>\r\n</Configuration>\r\n";
    }
    enum Flag : std::uint32_t {
        UserGuard=1,PathGuard=2,InputDenied=4,OutputWritable=8,ScratchWritable=16,
        AdaptersInspected=32,NoUpNonLoopback=64,HardwareD3D11=128
    };
    inline constexpr std::uint32_t AllFlags=255;
    struct GuestPacket {
        std::array<char,8> magic{'W','W','S','B','0','0','0','1'};
        Nonce nonce{};
        Digest helper{};
        std::uint32_t flags=0,featureLevel=0,hresult=0,reserved=0;
    };
    static_assert(sizeof(GuestPacket)==72);
    inline bool Valid(const GuestPacket &packet,const Nonce &nonce,const Digest &helper) {
        return packet.magic==GuestPacket{}.magic && packet.nonce==nonce && packet.helper==helper
            && (packet.flags&~AllFlags)==0 && packet.reserved==0
            && (packet.featureLevel==0 || packet.featureLevel==0xb000)
            && (!(packet.flags&HardwareD3D11) || (packet.featureLevel==0xb000 && (packet.hresult&0x80000000U)==0));
    }
    inline bool Passed(const GuestPacket &packet,const Nonce &nonce,const Digest &helper) {
        return Valid(packet,nonce,helper) && packet.flags==AllFlags;
    }
}
