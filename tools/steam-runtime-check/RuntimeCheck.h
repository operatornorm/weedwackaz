#pragma once
#include "SteamInviteBindings.h"

namespace WWRuntimeCheck {
    using namespace Dynamite::Invites;
    struct Result {
        const char *status = "untrusted_module";
        bool steamAttempted = false, initialized = false, bound = false;
        bool registered = false, detached = false, shutdown = false;
        bool Passed() const { return initialized && bound && registered && detached && shutdown; }
    };
    // Standalone helper only, never used inside MGSV. Init/Shutdown belong to this
    // process. The caller pins/retains the module and keeps callback storage alive
    // until process exit, including failed SDK unregistration/shutdown paths.
    inline Result Run(bool modulePinned, bool (*initialize)(), void (*shutdown)(), const Api &api, CallbackQueue &callback) {
        Result result;
        if (!modulePinned) return result;
        result.status = "missing_exports";
        if (!initialize || !shutdown || !api.Complete()) return result;
        result.status = "invalid_callback_storage";
        if (callback.Registered() || !callback.LayoutMatches()) return result;
        result.status = "steam_initialization_failed";
        result.steamAttempted = true;
        if (!initialize()) return result;
        result.initialized = true;
        Context context;
        const auto binding = Bind(api, context);
        result.status = "steam_context_not_ready";
        if (binding == BindStatus::WrongApp) result.status = "wrong_app_id";
        if (binding == BindStatus::InvalidLocalIdentity) result.status = "invalid_local_identity";
        if (binding == BindStatus::Bound) {
            result.bound = true;
            Channel channel(context, callback);
            result.registered = channel.StartObserving();
            result.detached = channel.Stop() && !callback.Registered();
            result.status = result.registered ? "callback_cleanup_failed" : "callback_registration_failed";
            if (!result.detached) return result; // Retain initialized module and callback until process exit.
            if (result.registered) result.status = "interfaces_and_registration_verified";
        }
        shutdown(); result.shutdown = true;
        return result;
    }
    inline std::string Json(const Result &result) {
        const auto flag=[](bool value) { return value ? "true" : "false"; };
        return std::string("{\"schema\":1,\"kind\":\"ww_steam_runtime_check\",\"result\":\"")+(result.Passed()?"PASS":"FAIL")+
            "\",\"status\":\""+result.status+"\",\"steam_context_attempted\":"+flag(result.steamAttempted)+
            ",\"steam_initialized\":"+flag(result.initialized)+",\"interfaces_bound\":"+flag(result.bound)+
            ",\"callback_registered\":"+flag(result.registered)+",\"callback_unregistered\":"+flag(result.detached)+
            ",\"steam_shutdown_called\":"+flag(result.shutdown)+
            ",\"game_launched\":false,\"invitations_sent\":0,\"real_callback_delivery_verified\":false,\"co_op_verified\":false}\n";
    }
}
