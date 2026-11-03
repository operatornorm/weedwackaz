#include "Plan.h"
#include <cstdlib>
#include <iostream>
using namespace WWSandbox;
void check(bool value,const char *text) { if(!value){std::cerr<<text<<'\n';std::exit(1);} }
int main(int argc,char **argv) {
    const auto nonce=ParseNonce(std::string(32,'a'));check(nonce.has_value(),"nonce accepted");
    check(!ParseNonce(std::string(32,'0')) && !ParseNonce(std::string(32,'A')) && !ParseNonce("../file"),"unsafe nonce rejected");
    const auto config=Configuration(L"C:\\case & test\\Input",L"C:\\case & test\\Output",*nonce);
    if(argc==2 && std::string_view(argv[1])=="--config"){
        check(config.has_value(),"configuration available");
        std::cout<<std::string(config->begin(),config->end());return 0;
    }
    check(config && config->find(L"<Networking>Disable</Networking>")!=config->npos && config->find(L"<ReadOnly>true</ReadOnly>")!=config->npos,"network off and bounded read-only input mapping");
    check(config->find(L"case &amp; test")!=config->npos && config->find(L"--guest "+std::wstring(32,L'a'))!=config->npos,"escaped local paths and exact nonce argument");
    check(!Configuration(L"\\\\server\\share",L"C:\\out",*nonce) && !Configuration(L"C:\\x\n",L"C:\\out",*nonce),"network/control paths rejected");
    check(!Configuration(L"C:\\same",L"C:\\same",*nonce),"mapping roots must differ");
    Digest helper{};helper[0]=1;
    GuestPacket report;report.nonce=*nonce;report.helper=helper;report.flags=AllFlags;report.featureLevel=0xb000;
    check(Passed(report,*nonce,helper),"complete matching synthetic report accepted");
    for(std::uint32_t bit=1;bit<=HardwareD3D11;bit<<=1) {
        auto bad=report;bad.flags^=bit;check(!Passed(bad,*nonce,helper),"every missing observation blocks PASS");
    }
    auto bad=report;bad.nonce[0]^=1;check(!Passed(bad,*nonce,helper),"stale nonce rejected");
    bad=report;bad.helper[0]^=1;check(!Passed(bad,*nonce,helper),"different helper rejected");
    bad=report;bad.flags|=256;check(!Passed(bad,*nonce,helper),"unknown observation rejected");
    bad=report;bad.magic[0]='X';check(!Passed(bad,*nonce,helper),"bad report schema rejected");
    bad=report;bad.hresult=0x80004005;check(!Passed(bad,*nonce,helper),"failed D3D result cannot PASS");
    bad=report;bad.featureLevel=0xa000;check(!Passed(bad,*nonce,helper),"insufficient D3D level rejected");
    std::cout<<"PASS: Sandbox plan and guest report validation, synthetic only\n";
}
