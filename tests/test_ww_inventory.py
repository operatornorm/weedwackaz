"""Collector checks with synthetic engine state, not game QA."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_dynamite_lifecycle import Lua

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "qa/lua/ww_inventory.lua"
sys.path.insert(0, str(ROOT / "tools"))
from extract_ww_inventory import extract


def fixture(body):
    return r'''
local calls = 0
local originalLoadfile = loadfile
local module
local messages, notifications = {}, {}
TppUiCommand = {AnnounceLogView = function(text) notifications[#notifications + 1] = text end}
Dynamite = {
    Log = function(text) messages[#messages + 1] = text end,
    IsHost = function() calls = calls + 1; return true end,
    IsClient = function() calls = calls + 1; return false end,
    CreateClientSession = function() error("collector must not create sessions") end
}
TppNetworkUtil = {IsHost = function() return true end, IsSessionConnect = function() return false end}
TppGameStatus = {IsSet = function(owner, flag)
    assert(owner == "Mission" and flag == "S_IS_ONLINE"); return false end}
TppQuest = {Clear = function() error("collector must not clear quests") end}
TppQuestList = {questList = {
    {name = "ruins_q19010", id = 19},
    {name = "C:/Users/PC_PATH_SECRET/Steam/userdata/1234567"},
    {name = "ACCOUNT_SECRET_DO_NOT_EXPORT"}
}, questPackList = {ruins_q19010 = "/Assets/tpp/pack/quest/ruins_q19010.fpk"}}
vars = {missionCode = 30010, locationCode = 10}
mvars = {mis_missionName = "s30010", seq_currentSequence = "Seq_Game_Main", qst_example = {}}
svars = {seq_sequence = 12}
os.time = function() return 123 end
io.open = function() error("collector must not use Lua file IO") end
debug = nil
local function capturedReport()
    local chunks = {}
    for _, text in ipairs(messages) do
        local encoded = text:match("^%[WWINV1%] DATA [%d%-]+ %d+ ([0-9a-f]+)$")
        if encoded then
            chunks[#chunks + 1] = encoded:gsub("%x%x", function(pair)
                return string.char(tonumber(pair, 16))
            end)
        end
    end
    return table.concat(chunks)
end
module = assert(originalLoadfile(__MODULE_PATH__))()
__BODY__
'''.replace("__MODULE_PATH__", json.dumps(str(COLLECTOR), ensure_ascii=False)).replace("__BODY__", body)


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = Lua()

    def test_import_is_inert(self):
        self.lua.execute(fixture('assert(calls == 0 and #notifications == 0 and #messages == 0)'))

    def test_collect_displays_status(self):
        self.lua.execute(fixture(r'''
assert(module.Collect())
assert(notifications[1] == "WW inventory: collector started")
assert(notifications[#notifications] == "WW inventory: report sent to Dynamite log")
'''))

    def test_probe_checks_binding_without_inventory_queries(self):
        self.lua.execute(fixture(r'''
assert(module.Probe())
assert(calls == 0)
assert(notifications[1] == "WW inventory: binding works")
assert(not table.concat(messages):find("[WWINV1]", 1, true))
'''))

    def test_missing_ui_still_exports_through_native_log(self):
        self.lua.execute(fixture(r'''
TppUiCommand = nil
assert(module.Collect())
assert(#notifications == 0)
assert(capturedReport():find("report.complete" .. string.char(9) .. "true", 1, true))
'''))

    def test_collects_known_metadata_without_exporting_private_strings(self):
        self.lua.execute(fixture(r'''
assert(module.Collect())
local report = capturedReport()
assert(report:find("runtime_metadata_only_not_a_gameplay_test", 1, true))
assert(report:find("state.vars.missionCode" .. string.char(9) .. "30010", 1, true))
assert(report:find("ruins_q19010", 1, true))
assert(report:find("query.Dynamite.IsHost" .. string.char(9) .. "true", 1, true))
assert(not report:find("PC_PATH_SECRET", 1, true))
assert(not report:find("1234567", 1, true))
assert(not report:find("ACCOUNT_SECRET_DO_NOT_EXPORT", 1, true))
assert(calls == 2)
'''))

    def test_missing_modules_and_cycles_are_reported(self):
        self.lua.execute(fixture(r'''
TppQuestList.questList.self = TppQuestList.questList
TppNetworkUtil = nil
assert(module.Collect())
local report = capturedReport()
assert(report:find("<cycle-or-shared-table>", 1, true))
assert(report:find("query.TppNetworkUtil.IsSessionConnect" .. string.char(9) .. "<unavailable>", 1, true))
'''))

    def test_large_registry_is_bounded_and_labeled_partial(self):
        self.lua.execute(fixture(r'''
TppQuestList.questList = {}
for i = 1, 10000 do TppQuestList.questList[i] = {name = "ruins_q" .. i} end
assert(module.Collect())
local report = capturedReport()
assert(#report <= 512 * 1024)
assert(report:find("report.truncated" .. string.char(9) .. "true", 1, true))
for _, message in ipairs(messages) do assert(#message < 900) end
'''))

    def test_long_identifiers_are_limited_before_serialization(self):
        self.lua.execute(fixture(r'''
TppQuestList.questList = {{name = string.rep("huge", 200000) .. "_q1"}}
assert(module.Collect())
local report = capturedReport()
assert(#report <= 512 * 1024)
assert(report:find("<string-length-limit>", 1, true))
assert(report:find("report.truncated" .. string.char(9) .. "true", 1, true))
'''))

    def test_lua_file_access_and_source_location_are_not_required(self):
        self.lua.execute(fixture(r'''
io = nil
debug = nil
assert(module.Collect())
assert(capturedReport():find("report.complete", 1, true))
'''))

    def test_missing_native_logger_is_reported_without_file_fallback(self):
        self.lua.execute(fixture(r'''
Dynamite.Log = nil
assert(module.Collect() == false)
assert(calls == 0)
assert(notifications[#notifications] == "WW inventory: native log API unavailable")
'''))

    def test_native_logger_exception_leaves_no_end_or_success_message(self):
        self.lua.execute(fixture(r'''
Dynamite.Log = function(text)
    if text:find("[WWINV1] DATA", 1, true) then error("synthetic log failure") end
    messages[#messages + 1] = text
end
assert(module.Collect() == false)
assert(notifications[#notifications] == "WW inventory: native log export failed")
assert(not table.concat(messages):find("[WWINV1] END", 1, true))
'''))

    def test_repeated_captures_have_distinct_ids(self):
        self.lua.execute(fixture(r'''
local ok1, id1 = module.Collect()
local ok2, id2 = module.Collect()
assert(ok1 and ok2 and id1 == "123-1" and id2 == "123-2")
'''))

    def test_real_lua_export_round_trips_through_python_extractor(self):
        with tempfile.TemporaryDirectory(prefix="ww-native-log-") as directory:
            log = Path(directory) / "synthetic-native.log"
            code = fixture(r'''
assert(module.Collect())
local file = assert(originalOpen(__LOG_PATH__, "wb"))
file:write("UNRELATED_PC_PATH_SECRET SteamID 1234567\n")
for _, text in ipairs(messages) do
    file:write("[synthetic timestamp] [dynamite] [info] [lua] " .. text .. "\n")
end
assert(file:close())
'''.replace("__LOG_PATH__", json.dumps(str(log))))
            self.lua.execute(code.replace(
                'local originalLoadfile = loadfile',
                'local originalLoadfile = loadfile\nlocal originalOpen = io.open'))
            with log.open("rb") as source:
                report = extract(source)
            self.assertIn(b"ruins_q19010", report)
            self.assertIn(b"state.vars.missionCode\t30010\n", report)
            self.assertNotIn(b"UNRELATED_PC_PATH_SECRET", report)
            self.assertNotIn(b"1234567", report)
            self.assertTrue(report.endswith(b"report.complete\ttrue\n"))


if __name__ == "__main__":
    unittest.main()
