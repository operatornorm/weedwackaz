# Opt-in local status bridge

Patch 0005 finishes the first local observation transport. It uses a fixed status
file, not a listening socket. No game commands, Steam actions, save operations or
arbitrary paths can be sent through it.

The normal CMake build compiles DYNAMITE_QA_STATUS_FILE=OFF. Its native Due/Publish
bindings always return false, including when request files exist. An explicit QA
build additionally requires an executable-relative dynamite/wwqa/request.txt,
which must be a regular 39-byte file: WWQA1, newline, 32 lowercase hex run-ID bytes,
newline. Symlinks/special files are rejected. Future authorized test preparation
must generate a fresh run ID; never reuse an old capture request.

TppMain calls WWRuntimeBridge.Poll after normal engine/subscript updates. The
native due gate binds the first caller's lua_State and thread and rejects changes.
This is caller affinity, not independent proof of Windows OS-main-thread identity.
Only one publication is permitted per 500ms grant. The actual observation is
filtered/encoded in that Lua context. Native code enforces a 16KiB schema/field/type
allowlist and denies every readiness proof before publishing.

The fixed status.json is replaced through an exclusively created temporary file.
It contains run ID, generation, frame ID, publication tick and the observation.
Counters are decimal strings. Reads never refresh them. Reload and termination
suspend capture before callbacks; repeated suspension is idempotent. A stopped
request cannot resume without a different run ID. No threads or sockets are
started from DllMain, and no Lua state is accessed by a transport thread.

tools/mgsv_observer_smoke.py only reads the status file. It rejects nonregular
inputs, duplicate/invalid JSON, wrong run/world/generation, rewritten/nonadvancing
frames, stale native samples, missing observations and claimed verification.
It requires multiple progressing samples and fresh progress at the end, so a
running poll timer or a late frozen file cannot pass. PASS means only that the
local observation channel advanced in the requested context; co_op_verified
always remains false. It launches/stops no processes and writes only an exclusive
report selected by its caller outside the status directory.

The source uses the unchanged MIT-licensed Coop Anything JSON helper pinned to
cbb37dc16c164877f50a8a00af673fb1874fddbb. Attribution and license are retained under
hook/third_party/coopbridge. No RPC server or external software was installed.

Tests cover the actual publisher/filesystem implementation, native default-disabled
bindings in a real Lua VM, actual Lua encoding decoded independently with Python,
actual update/reload/terminate placement, caller mismatch, repeated-stop fencing,
exclusive output, malformed/FIFO inputs, missing state and frozen-data controls.
Portable filesystem executions use the host POSIX branch; Windows behavior is
cross-built and still needs runtime validation.

Developer reproduction after applying all five patches:

    python3 build-support/export_status_bridge_patch.py --verify-only
    bash build-support/build-status-bridge-offline.sh /path/to/dynamite

The cloud build outputs a default-disabled DLL and an explicit-QA DLL plus QA
Windows/Linux installer packages. They are development artifacts; runtime save
isolation remains unverified, so no owner game launch is requested here.
