// The Python driver injects the actual production lifecycle method definitions.
#include "DynamiteSyncImpl/InitialVarSync.h"
#include <iostream>
#include <thread>

namespace spdlog {
    template <class... Args> void info(Args &&...) {}
}
namespace Dynamite {
    struct StubCore { void RemoveOpponentEmblemTexture() {} };
    struct StubHook { StubCore dynamiteCore; } stubHook;
    auto g_hook = &stubHook;
    struct DynamiteSyncImpl {
        InitialVarSync initialVarSync;
        std::vector<std::string> enemyVars{"solFovaSeed", "solFaceFova", "solBodyFova", "solRandomSeed"};
        std::jthread syncThread;
        unsigned packetNumber = 0, packetSeen = 0;
        void *steamUDPSocket = nullptr, *steamUDPAddress = nullptr, *steamUDPSocketInfo = nullptr;
        void SyncInit();
        void Init();
        void Stop();
        bool IsSynchronized();
    };
__SYNC_METHODS__
}

int main() {
    using namespace Dynamite;
    int failures = 0;
    auto check = [&](bool value, const char *description) {
        if (!value) { std::cerr << "FAIL: " << description << '\n'; ++failures; }
    };
    DynamiteSyncImpl sync;
    auto complete = [&] {
        const auto token = sync.initialVarSync.Generation();
        for (const auto &key : sync.enemyVars) sync.initialVarSync.Record(token, "svars", key, true);
    };
    check(!sync.IsSynchronized(), "fresh state is not synchronized");
    complete();
    check(!sync.IsSynchronized(), "unsolicited completion is ignored");
    sync.SyncInit();
    auto token = sync.initialVarSync.Generation();
    check(sync.initialVarSync.Pending().size() == 4, "all required handlers start pending");
    for (std::size_t i = 0; i < 3; ++i) sync.initialVarSync.Record(token, "svars", sync.enemyVars[i], true);
    sync.initialVarSync.Record(token, "gvars", sync.enemyVars[3], true);
    sync.initialVarSync.Record(token, "svars", "unrelated", true);
    sync.initialVarSync.Record(token, "svars", sync.enemyVars[3], false);
    check(!sync.IsSynchronized(), "partial and wrong-category completion is rejected");
    sync.initialVarSync.Record(token, "svars", sync.enemyVars[3], true);
    check(sync.IsSynchronized(), "all required successful handlers complete tracking");
    complete();
    check(sync.IsSynchronized(), "duplicate completion is harmless");
    sync.initialVarSync.Record(token, "svars", "unrelated", false);
    check(sync.IsSynchronized(), "unrelated variables do not poison tracking");
    sync.Stop();
    check(!sync.IsSynchronized(), "Stop invalidates completed tracking");
    complete();
    check(!sync.IsSynchronized(), "marks after Stop are ignored");
    sync.SyncInit(); complete(); sync.Init();
    check(!sync.IsSynchronized(), "Init invalidates completed tracking");
    sync.SyncInit(); complete();
    token = sync.initialVarSync.Generation();
    sync.SyncInit();
    for (const auto &key : sync.enemyVars) sync.initialVarSync.Record(token, "svars", key, true);
    check(!sync.IsSynchronized(), "overlapping previous-generation handlers are ignored");
    std::vector<std::jthread> writers;
    for (const auto &key : sync.enemyVars) writers.emplace_back([&, key] {
        sync.initialVarSync.Record(sync.initialVarSync.Generation(), "svars", key, true);
    });
    writers.clear();
    check(sync.IsSynchronized(), "concurrent required handler completions are tracked");
    sync.initialVarSync.Begin({});
    check(!sync.IsSynchronized(), "empty required set is not synchronization");
    if (failures) return 1;
    std::cout << "PASS: actual initial-sync lifecycle and required-handler tracking\n";
}
