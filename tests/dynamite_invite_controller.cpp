#include "steam_invite_fake_api.h"
#include "SteamInviteController.h"
#include <cstdlib>
#include <iostream>
#include <thread>
#include <type_traits>

using namespace Dynamite::Invites;
void check(bool value, const char *message) { if (!value) { std::cerr << message << '\n'; std::exit(1); } }
ActivationProof proofs{true, true, true, true}; // Synthetic boundary only; never production evidence.
Intent guest(char nonce='a') { return {Fixture::Friend, "afghanistan-normal", std::string(32,nonce), 1, 1200}; }
Intent host() { auto value=guest(); value.host=Fixture::Self; return value; }
WorldFrame frame(std::uint64_t sample, bool ready=true, std::uint64_t generation=1) {
    return {sample,generation,proofs,true,true,ready,ready,true,ready?"afghanistan-normal":""};
}
Context context() {
    Api api{SteamClient,SteamAPI_GetHSteamUser,SteamAPI_GetHSteamPipe,SteamAPI_ISteamClient_GetISteamFriends,
        SteamAPI_ISteamClient_GetISteamUser,SteamAPI_ISteamClient_GetISteamUtils,SteamAPI_ISteamUtils_GetAppID,
        SteamAPI_ISteamUser_GetSteamID,SteamAPI_ISteamFriends_GetFriendRelationship,SteamAPI_ISteamFriends_InviteUserToGame,
        SteamAPI_RegisterCallback,SteamAPI_UnregisterCallback};
    Context result; check(Bind(api,result)==BindStatus::Bound,"fixture context bound"); return result;
}
bool cold(Controller &controller, const Intent &value, std::uint64_t now=1000) {
    const auto text=Encode(value); const std::array<std::string_view,2> args{"mgsvtpp.exe",text};
    return controller.AcceptCold(args,now);
}
void warm(CallbackQueue &callback, const Intent &value) { auto event=Fixture::Event(value.host,Encode(value)); callback.Run(&event); }
void release(Controller &controller, std::uint64_t sample=100, std::uint64_t now=1001) {
    check(!controller.Stop(),"owned session requires cleanup before stopped");
    auto f=frame(sample,true,sample); f.contracts={}; f.noForeignSession=false;
    const auto action=controller.Next(f,now);
    check(action && action->kind==ActionKind::ReleaseOwned,"lost proofs cannot block owned cleanup");
    check(controller.Complete(*action,true) && controller.Stop(),"observed release finishes stop");
    check(Fixture::registered==nullptr,"callback unregistered before fixture destruction");
}
void defaults() {
    auto ctx=context(); Fixture::calls=0; CallbackQueue callback; Controller controller(ctx,callback);
    static_assert(!std::is_copy_constructible_v<Controller> && !std::is_move_constructible_v<Controller>);
    check(Fixture::calls==0 && controller.Status()->phase==Phase::Stopped,"constructor has no SDK side effects");
    check(!controller.Start({}) && Fixture::calls==0,"default proofs block callback registration");
    check(!controller.RequestHost(host(),1000) && !cold(controller,guest()),"inactive control rejects intents");
    check(!controller.Next(frame(1),1000) && Fixture::calls==0,"inactive frame has no engine or SDK action");
    check(controller.Stop() && controller.Stop() && Fixture::calls==0,"default stop idempotent without SDK calls");
}
void loading() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    warm(callback,guest()); auto f=frame(1,false); f.safeToPrepare=false;
    check(!controller.Next(f,1000) && controller.Status()->pending==guest(),"warm intent deferred while unsafe to load");
    f=frame(2,false); const auto prepare=controller.Next(f,1001);
    check(prepare && prepare->kind==ActionKind::PrepareTarget && prepare->session==guest(),"one target preparation action");
    check(!controller.Next(frame(3),1001),"outstanding action cannot repeat");
    check(controller.Complete(*prepare,true),"load action acknowledged");
    check(!controller.Next(frame(4),1001),"ready data from previous engine generation cannot connect");
    const auto connect=controller.Next(frame(5,true,2),1002);
    check(connect && connect->kind==ActionKind::ConnectGuest && connect->session.host==Fixture::Friend,"fresh loaded target yields guest connection target");
    check(controller.Complete(*connect,true) && controller.Status()->phase==Phase::AwaitingPeer,"connect acknowledgement is not verified co-op");
    check(!controller.Next(frame(6,true,2),1003),"transport request never repeated or promoted to joined");
    check(!cold(controller,guest(),1003),"hot and cold duplicate intents deduplicated together");
    release(controller);
}
void cleanup() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    check(cold(controller,guest()),"cold intent"); const auto old=controller.Next(frame(1),1000);
    check(old && old->kind==ActionKind::ConnectGuest,"initial connect issued");
    check(controller.Cancel() && !controller.Next(frame(2),1001),"cancel retains outstanding ambiguous operation");
    check(cold(controller,guest('b'),1001),"new accepted selection queued behind cleanup");
    auto forged=*old; ++forged.ticket;
    check(!controller.Complete(forged,true),"stale action acknowledgement rejected");
    check(controller.Complete(*old,false) && !controller.Complete(*old,true),"failed action acknowledged once");
    auto close=controller.Next(frame(3),1001);
    check(close && close->kind==ActionKind::ReleaseOwned && close->session.session==std::string(32,'a') && close->ownership==old->ownership,"cleanup remains bound to old context");
    check(controller.Complete(*close,false),"failed cleanup recorded");
    check(!controller.Next(frame(4),1001) && controller.Status()->cleanupOwned,"failed cleanup cannot clear ownership");
    check(!controller.Start(proofs) && !controller.Complete(*close,true),"late ack and restart cannot bypass cleanup");
    check(controller.RetryCleanup(),"explicit cleanup retry"); const auto retry=controller.Next(frame(5),1001);
    check(retry && retry->ticket>close->ticket && controller.Complete(*retry,true),"retry has fresh ticket and releases old context");
    check(controller.Status()->pending==guest('b'),"old cleanup cannot erase newer pending selection");
    const auto next=controller.Next(frame(6),1002);
    check(next && next->session.session==std::string(32,'b') && next->ownership>old->ownership,"latest selection has independent ownership after cleanup");
    check(!controller.Stop(),"stop awaits in-flight action");
    check(controller.Complete(*next,true),"late successful connect is retained for release, not activated");
    auto close2=controller.Next(frame(7),1002); check(close2 && controller.Complete(*close2,true) && controller.Stop(),"stop drains late side effects");
    check(controller.Start(proofs),"restart after complete cleanup");
    check(cold(controller,guest('c'),1003),"new restart intent"); const auto newAction=controller.Next(frame(1),1003);
    check(newAction && newAction->run>old->run && newAction->ticket>old->ticket && !controller.Complete(*old,true),"run and action IDs never alias on restart");
    check(controller.Complete(*newAction,true),"new action acknowledgement"); release(controller,100,1004);
}
void hosting() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    check(!controller.RequestHost(guest(),1000),"host descriptor must use local identity");
    check(controller.RequestHost(host(),1000),"local host selection");
    check(!controller.Next(frame(1,false),1000),"hosting waits for verified selected world");
    const auto start=controller.Next(frame(2),1000); check(start && start->kind==ActionKind::StartHost,"host creation action");
    check(controller.Complete(*start,true),"host creation observed");
    check(controller.Send(Fixture::Friend,frame(3),1000) && Fixture::sends==1,"explicit host invite sends once");
    check(!controller.Send(Fixture::Friend,frame(4),1000) && Fixture::sends==1,"duplicate send not retried");
    check(!controller.Next(frame(5),1200) && controller.Status()->phase==Phase::Hosting,"invite TTL does not destroy host world");
    check(!controller.Send(Fixture::Friend,frame(6),1200),"expired descriptor cannot invite");
    check(controller.RenewHost(1300,1200) && controller.Send(Fixture::Friend,frame(7),1200) && Fixture::sends==2,"explicit expiry renewal can send again");
    auto value=guest('b'); value.expires=1350; warm(callback,value);
    const auto close=controller.Next(frame(8),1201);
    check(close && close->kind==ActionKind::ReleaseOwned && close->role==Role::Host,"accepted invite retires owned host before changing role");
    check(controller.Status()->role==Role::Host && controller.Status()->pending==value,"active role preserved during old host cleanup");
    check(controller.Complete(*close,true),"old host released");
    const auto join=controller.Next(frame(9),1202);
    check(join && join->role==Role::Guest && join->session==value,"host can become guest without config rewrite");
    check(controller.Complete(*join,true),"guest action acknowledged"); release(controller,100,1203);
}
void safety() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    check(!cold(controller,host()),"self invite rejected");
    const std::array<std::string_view,2> mgo{"mgsvtpp.exe","+connect mgo"};
    check(!controller.AcceptCold(mgo,1000) && !controller.Status()->pending,"ordinary MGO launch arguments not claimed");
    Fixture::relation=1; check(!cold(controller,guest()),"cold invite requires current friendship"); Fixture::relation=3;
    check(cold(controller,guest()),"intent accepted"); Fixture::relation=1;
    check(!controller.Next(frame(1),1001) && !controller.Status()->cleanupOwned,"friend removed before dispatch prevents engine action");
    Fixture::relation=3;
    for (int missing=0;missing<4;++missing) {
        check(cold(controller,guest(static_cast<char>('b'+missing)),1002),"new intent");
        auto f=frame(2+missing);
        if(missing==0)f.contracts.saveIsolation=false;
        if(missing==1)f.contracts.resourceContract=false;
        if(missing==2)f.contracts.peerProtocol=false;
        if(missing==3)f.contracts.mgoRouting=false;
        check(!controller.Next(f,1002) && !controller.Status()->cleanupOwned,"every missing contract prevents engine dispatch");
    }
    check(cold(controller,guest('f'),1003),"deferred expiring intent"); auto busy=frame(10,false); busy.safeToPrepare=false;
    check(!controller.Next(busy,1003),"busy load remains deferred");
    check(!controller.Next(frame(11),1200) && !controller.Status()->pending,"intent expires at exact deadline while loading");
    auto newer=guest('a'); newer.expires=1400; check(cold(controller,newer,1200),"new valid intent");
    auto foreign=frame(12); foreign.noForeignSession=false;
    check(!controller.Next(foreign,1200) && !controller.Status()->cleanupOwned,"unowned MGO/FOB session blocks without cleanup action");
    check(controller.Stop(),"no engine ownership means stop is complete");
}
void boundaries() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    auto newer=guest(); newer.epoch=2; check(cold(controller,newer),"new epoch accepted");
    auto old=guest(); old.expires=1250; check(!cold(controller,old),"older epoch cannot replace newer selection");
    auto changed=newer; changed.target="africa-normal"; changed.expires=1250;
    check(!cold(controller,changed),"target is immutable within session epoch");
    auto renewed=newer; renewed.expires=1250; check(cold(controller,renewed),"renewed expiry accepted");
    const auto prepare=controller.Next(frame(1,false),1001); check(prepare.has_value(),"prepare issued");
    check(!controller.Next(frame(1),1002),"replayed frame cannot dispatch twice");
    check(!controller.Next(frame(2),1000) && controller.Status()->clockInvalid,"clock rollback invalidates control");
    check(controller.Complete(*prepare,true),"in-flight action still acknowledged after rollback");
    auto f=frame(3); f.contracts={};
    const auto close=controller.Next(f,1000);
    check(close && close->kind==ActionKind::ReleaseOwned && controller.Complete(*close,true),"clock failure still permits owned cleanup");
    check(controller.Stop() && !controller.Start(proofs),"invalid clock cannot silently restart or refresh old intents");
}
void threads() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    check(cold(controller,guest()),"intent accepted"); const auto action=controller.Next(frame(1),1000); check(action.has_value(),"action issued");
    const auto before=Fixture::calls; bool rejected=false;
    std::thread worker([&] {
        rejected=!controller.Start(proofs) && !controller.RequestHost(host(),1000) && !cold(controller,guest('b'))
            && !controller.Next(frame(2),1000) && !controller.Complete(*action,true)
            && !controller.Send(Fixture::Friend,frame(3),1000) && !controller.RenewHost(1250,1000)
            && !controller.Cancel() && !controller.RetryCleanup() && !controller.Stop() && !controller.Status();
    }); worker.join();
    check(rejected && Fixture::calls==before,"foreign thread cannot read or mutate controller or call SDK");
    check(controller.Complete(*action,true),"owner acknowledges action"); release(controller);
}
void generation() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    check(cold(controller,guest()),"intent accepted"); const auto action=controller.Next(frame(1),1000);
    check(action && !controller.Next(frame(2,true,2),1001),"world changes while connect outstanding");
    check(controller.Complete(*action,true),"old generation action can settle without reviving join");
    const auto close=controller.Next(frame(3,true,2),1001);
    check(close && close->kind==ActionKind::ReleaseOwned,"old connection generation cannot become current world");
    check(controller.Complete(*close,true),"old generation released");
    auto value=host(); value.session=std::string(32,'b');
    check(controller.RequestHost(value,1002),"new host requested"); const auto start=controller.Next(frame(4,true,2),1002);
    check(start && controller.Complete(*start,true),"host created in current generation");
    check(!controller.Send(Fixture::Friend,frame(5,true,3),1002) && Fixture::sends==0,"world change prevents host invitation");
    const auto hostClose=controller.Next(frame(6,true,3),1002);
    check(hostClose && hostClose->kind==ActionKind::ReleaseOwned && controller.Complete(*hostClose,true),"host generation change releases only old owned context");
    check(controller.Stop(),"generation scenario stopped");
}
void context_loss() {
    CallbackQueue callback; Controller controller(context(),callback);
    Fixture::registeredAck=false;
    check(!controller.Start(proofs) && !controller.Status()->running && Fixture::registered==nullptr,"registration failure cannot activate controller");
    Fixture::registeredAck=true; check(controller.Start(proofs),"registration retry after explicit cleanup");
    check(cold(controller,guest()),"intent accepted"); const auto action=controller.Next(frame(1),1000);
    check(action && controller.Complete(*action,true),"guest transport issued");
    Fixture::app=480;
    const auto close=controller.Next(frame(2),1001);
    check(close && close->kind==ActionKind::ReleaseOwned,"context/app change prevents continued use and retains cleanup");
    check(controller.Complete(*close,true),"owned context released");
    Fixture::unregisterAck=false;
    check(!controller.Stop() && !controller.Start(proofs),"unregister failure blocks restart");
    Fixture::unregisterAck=true; Fixture::app=AppId;
    check(controller.Stop() && controller.Start(proofs) && controller.Stop(),"explicit unregister retry releases callback lifetime");
}
void high_water() {
    CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
    auto value=host(); value.epoch=2;
    check(controller.RequestHost(value,1000),"host epoch two selected"); const auto start=controller.Next(frame(1),1000);
    check(start && controller.Complete(*start,true),"host epoch two created");
    auto stale=host(); stale.expires=1400;
    check(!controller.RequestHost(stale,1200),"expired history cannot erase owned epoch high-water");
    check(controller.RenewHost(1450,1200),"owned invitation renewed");
    auto shortened=value; shortened.expires=1400;
    check(!controller.RequestHost(shortened,1200),"renewal cannot roll back active descriptor expiry");
    release(controller,100,1201);
}
Controller *reentryController=nullptr;
int nestedCalls=0;
int reentrantRelationship(std::intptr_t, SteamId) {
    if (reentryController) {
        ++nestedCalls;
        check(!reentryController->Cancel() && !reentryController->Stop() && !reentryController->Status()
            && !reentryController->RequestHost(host(),1000) && !reentryController->Next(frame(999),1000),
            "SDK reentrancy cannot mutate or observe an operation in progress");
    }
    return 3;
}
void reentrancy() {
    auto ctx=context(); ctx.api.relationship=reentrantRelationship;
    CallbackQueue callback; Controller controller(ctx,callback); reentryController=&controller;
    check(controller.Start(proofs) && cold(controller,guest()),"intent accepted while SDK attempts reentry");
    const auto action=controller.Next(frame(1),1000);
    check(action && action->kind==ActionKind::ConnectGuest && controller.Complete(*action,true),"reentrant SDK cannot corrupt pending selection");
    check(nestedCalls>=3,"relationship reentry actually exercised");
    reentryController=nullptr; release(controller);
}
void active_world() {
    for(int invalid=0;invalid<6;++invalid) {
        CallbackQueue callback; Controller controller(context(),callback); check(controller.Start(proofs),"start");
        check(controller.RequestHost(host(),1000),"host selected"); const auto action=controller.Next(frame(1),1000);
        check(action && controller.Complete(*action,true),"host created");
        auto f=frame(2);
        if(invalid==0)f.noForeignSession=false;
        if(invalid==1)f.sidecarReady=false;
        if(invalid==2)f.target="africa-normal";
        if(invalid==3)f.targetVerified=false;
        if(invalid==4)f.playable=false;
        if(invalid==5)f.contracts.mgoRouting=false;
        const auto sends=Fixture::sends;
        check(!controller.Send(Fixture::Friend,f,1001) && Fixture::sends==sends,"negative active world flags prevent invite sending");
        f.sample=3;
        if(invalid<3 || invalid==5) {
            f=frame(3); // The invalidating observation must survive later recovery.
            const auto close=controller.Next(f,1001);
            check(close && close->kind==ActionKind::ReleaseOwned,"foreign session/sidecar loss/wrong target retires only owned context");
            check(controller.Complete(*close,true) && controller.Stop(),"invalid active context released");
        } else {
            check(!controller.Next(f,1001) && controller.Status()->phase==Phase::Hosting,"temporary unplayable/unknown world cannot invite but does not destroy host");
            release(controller);
        }
    }
}
int main(int argc,char **argv) {
    check(argc==2,"scenario required"); const std::string name=argv[1];
    if(name=="defaults")defaults(); else if(name=="loading")loading(); else if(name=="cleanup")cleanup();
    else if(name=="hosting")hosting(); else if(name=="safety")safety(); else if(name=="boundaries")boundaries();
    else if(name=="threads")threads(); else if(name=="generation")generation();
    else if(name=="context_loss")context_loss(); else if(name=="high_water")high_water();
    else if(name=="reentrancy")reentrancy();
    else if(name=="active_world")active_world();
    else check(false,"unknown scenario");
    check(Fixture::registered==nullptr,"all scenarios unregister callbacks");
    std::cout<<"PASS: synthetic invite controller "<<name<<'\n';
}
