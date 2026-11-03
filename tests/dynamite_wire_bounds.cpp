// Portable checks against the header used by the production sender/receiver.
#include "DynamiteSyncImpl/WireBounds.h"

#include <cstdint>
#include <iostream>
#include <limits>

int main() {
    using namespace Dynamite::Wire;
    int failures = 0;
    auto check = [&failures](bool condition, const char *description) {
        if (!condition) {
            std::cerr << "FAIL: " << description << '\n';
            ++failures;
        }
    };
    check(!CanSendPayload(0), "empty payload rejected");
    for (std::size_t size = 1; size <= MaxPayloadSize; ++size) {
        check(CanSendPayload(size), "in-range sender payload accepted");
        const auto received = PayloadSize(static_cast<std::int32_t>(size + HeaderSize));
        check(received && *received == size, "sender and receiver agree on exact payload length");
    }
    for (std::size_t size = MaxPayloadSize + 1; size <= MaxPayloadSize + HeaderSize; ++size) {
        check(!CanSendPayload(size), "old oversized sender window rejected");
        check(!PayloadSize(static_cast<std::int32_t>(size + HeaderSize)),
              "receiver rejects oversized frame");
    }
    check(!CanSendPayload(std::numeric_limits<std::size_t>::max()), "size_t maximum rejected");
    for (std::int32_t size = -1; size <= static_cast<std::int32_t>(HeaderSize); ++size) {
        check(!PayloadSize(size), "empty or truncated frame rejected");
    }
    check(!PayloadSize(std::numeric_limits<std::int32_t>::min()), "negative minimum rejected");
    check(!PayloadSize(std::numeric_limits<std::int32_t>::max()), "positive maximum rejected");
    if (failures) return 1;
    std::cout << "PASS: packet-size boundaries and exact payload lengths\n";
    return 0;
}
