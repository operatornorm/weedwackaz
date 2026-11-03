"""Execute the real upstream Lua module with engine stubs, not game clients.

Set DYNAMITE_SOURCE_DIR to a patched v0.6.0 checkout. The host's installed Lua
library is used; the approved cloud container provides Lua 5.1.5. Engine APIs
remain stubs, so these are not game-runtime tests.
"""

import ctypes
import ctypes.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(os.environ.get(
    "DYNAMITE_SOURCE_DIR", str(Path(__file__).resolve().parents[2] / "dynamite")))
MODULE = SOURCE / "moddata/standalone/TppMain.lua"


class Lua:
    def __init__(self):
        name = os.environ.get("DYNAMITE_LUA_LIBRARY")
        if not name:
            for version in ("lua5.1", "lua5.4", "lua5.3"):
                name = ctypes.util.find_library(version)
                if name:
                    break
        if not name:
            raise RuntimeError("A Lua shared library is required; no tests were run")
        self.lib = ctypes.CDLL(name)
        self.lib.luaL_newstate.restype = ctypes.c_void_p
        self.lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        self.lib.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.luaL_loadstring.restype = ctypes.c_int
        self.lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_size_t)]
        self.lib.lua_tolstring.restype = ctypes.c_void_p
        self.lib.lua_close.argtypes = [ctypes.c_void_p]
        if hasattr(self.lib, "lua_pcallk"):
            self.call = self.lib.lua_pcallk
            self.call.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
            self.extra = (0, None)
        else:
            self.call = self.lib.lua_pcall
            self.call.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int]
            self.extra = ()
        self.call.restype = ctypes.c_int

    def execute(self, code):
        state = self.lib.luaL_newstate()
        if not state:
            raise RuntimeError("Cannot create Lua state")
        try:
            self.lib.luaL_openlibs(state)
            status = self.lib.luaL_loadstring(state, code.encode("utf-8"))
            if status == 0:
                status = self.call(state, 0, 0, 0, *self.extra)
            if status:
                size = ctypes.c_size_t()
                pointer = self.lib.lua_tolstring(state, -1, ctypes.byref(size))
                error = ctypes.string_at(pointer, size.value).decode("utf-8", "replace")
                raise RuntimeError(error)
        finally:
            self.lib.lua_close(state)


def fixture(path, *, online=True, mission=10033, sequence=True, shadow=False):
    return """
local calls = {}
local function record(name) calls[#calls + 1] = name end
Tpp = {IsTypeFunc = function(value) return type(value) == "function" end}
TppScriptVars = {}
ScriptBlock = {}
Mission = {}
vars = {missionCode = %d}
TppGameStatus = {
    IsSet = function(owner, flag)
        assert(owner == "Mission" and flag == "S_IS_ONLINE")
        return %s
    end,
    Reset = function(owner, flag)
        assert(owner == "Mission" and flag == "S_IS_ONLINE")
        record("reset-online")
    end
}
Dynamite = {
    StopNearestEnemyThread = function() record("stop-targeting") end,
    ResetClientSessionState = function() record("reset-client") end
}
TppNetworkUtil = {
    SessionDisconnectPreparingMembers = function() record("disconnect") end,
    CloseSession = function() record("close") end
}
local main = assert(loadfile(%s))()
local scripts = {}
%s
%s
main.OnTerminate(scripts)
local expected = {%s}
assert(#calls == #expected, "wrong number of cleanup/callback calls")
for i, value in ipairs(expected) do
    assert(calls[i] == value, "wrong cleanup order at " .. i)
end
""" % (
        mission, str(online).lower(), json.dumps(str(path), ensure_ascii=False),
        ('scripts.sequence = {OnTerminate = function() record("sequence") end}'
         if sequence else 'scripts.sequence = {OnTerminate = "not a function"}'),
        ('scripts.IsCoop = function() error("used mission scripts as module") end'
         if shadow else ""),
        ",".join(json.dumps(value) for value in
                 ((["sequence"] if sequence else []) +
                  (["stop-targeting", "reset-online", "disconnect", "close", "reset-client"]
                   if online and mission == 10033 else []))),
    )


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODULE.is_file():
            raise RuntimeError("Set DYNAMITE_SOURCE_DIR to the patched source checkout")
        cls.lua = Lua()

    def test_online_coop_termination_calls_cleanup_after_sequence(self):
        self.lua.execute(fixture(MODULE))

    def test_offline_termination_preserves_callback_without_network_cleanup(self):
        self.lua.execute(fixture(MODULE, online=False))

    def test_non_coop_termination_does_not_close_a_session(self):
        self.lua.execute(fixture(MODULE, mission=30010))

    def test_non_function_callback_is_ignored_but_cleanup_runs(self):
        self.lua.execute(fixture(MODULE, sequence=False))

    def test_mission_script_field_cannot_shadow_module_predicate(self):
        self.lua.execute(fixture(MODULE, shadow=True))

    def test_original_shadowing_mutation_is_caught(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertEqual(source.count("function e.OnTerminate(subScripts)"), 1)
        source = source.replace("function e.OnTerminate(subScripts)",
                                "function e.OnTerminate(e)")
        source = source.replace("subScripts.sequence", "e.sequence")
        with tempfile.TemporaryDirectory() as directory:
            mutant = Path(directory) / "TppMain.lua"
            mutant.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "IsCoop"):
                self.lua.execute(fixture(mutant))


if __name__ == "__main__":
    unittest.main()
