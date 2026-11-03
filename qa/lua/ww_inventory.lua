-- Runtime metadata collector for an isolated Dynamite game copy.
-- Inert when required. Collect() queries known read-only state and sends a bounded,
-- framed report through Dynamite.Log. No Lua file IO is used. It does not test co-op.
local inventory = {}
local serial = 0
local maxEntries, maxDepth, maxBytes = 2048, 4, 512 * 1024

local function notify(message)
    local ui = rawget(_G, "TppUiCommand")
    if type(ui) == "table" and type(rawget(ui, "AnnounceLogView")) == "function" then
        pcall(ui.AnnounceLogView, message)
    end
    local api = rawget(_G, "Dynamite")
    if type(api) == "table" and type(rawget(api, "Log")) == "function" then
        -- Native Log writes to the DLL log only; it has no announce parameter.
        pcall(api.Log, message)
    end
end

local function field(object, name)
    if object == nil then return nil, "missing" end
    local ok, value = pcall(function() return object[name] end)
    if ok then return value, type(value) end
    return nil, "unavailable"
end

local function identifier(value)
    return type(value) == "string" and
        (value:match("^[_%a][_%w]*_q%d+[_%w]*$") or value:match("^q%d+$") or
         value:match("^[sfho]%d+$") or value:match("^Seq_[%w_]+$"))
end

local function scalar(value)
    local kind = type(value)
    if kind == "number" or kind == "boolean" then return tostring(value) end
    if kind == "nil" then return "<missing>" end
    if kind == "string" then
        if #value > 512 then return "<string-length-limit>" end
        if identifier(value) then return value end
        -- Game-internal pack names are metadata, not file contents or PC paths.
        if #value <= 512 and value:match("^/Assets/tpp/pack/[%w_./%-]+$") then return value end
        return "<string omitted>"
    end
    return "<" .. kind .. ">"
end

local function safeKey(key)
    if type(key) == "number" then return tostring(key) end
    if type(key) == "string" and #key <= 128 and key:match("^[%w_]+$") then return key end
    return nil
end

local function makeReport()
    local lines, bytes, nodes, truncated, visited = {}, 0, 0, false, {}
    local function emit(key, value)
        if value == "<string-length-limit>" then truncated = true end
        if #key + #value + 2 > maxBytes - 128 - bytes then truncated = true; return end
        local line = key .. "\t" .. value:gsub("[\r\n\t]", " ") .. "\n"
        lines[#lines + 1], bytes = line, bytes + #line
    end
    local function walk(path, value, depth)
        if nodes >= 8192 then truncated = true; return end
        nodes = nodes + 1
        if type(value) ~= "table" then emit(path, scalar(value)); return end
        if visited[value] then emit(path, "<cycle-or-shared-table>"); return end
        visited[value] = true
        if depth >= maxDepth then emit(path, "<depth-limit>"); truncated = true; return end
        local keys, scanned = {}, 0
        for key in next, value do
            scanned = scanned + 1
            if scanned > maxEntries then truncated = true; break end
            local text = safeKey(key)
            if text then keys[#keys + 1] = {key = key, text = text} end
        end
        table.sort(keys, function(a, b) return a.text < b.text end)
        emit(path .. ".recorded_keys", tostring(#keys))
        for _, item in ipairs(keys) do
            if bytes >= maxBytes - 128 then truncated = true; break end
            walk(path .. "." .. item.text, rawget(value, item.key), depth + 1)
        end
    end
    local function module(name)
        local value = rawget(_G, name)
        if value == nil and type(package.loaded) == "table" then value = rawget(package.loaded, name) end
        emit("module." .. name, type(value))
        if type(value) == "table" then
            local keys, scanned = {}, 0
            for key, item in next, value do
                scanned = scanned + 1
                if scanned > maxEntries then truncated = true; break end
                local text = safeKey(key)
                if text then keys[#keys + 1] = {text = text, kind = type(item)} end
                if #keys >= maxEntries then truncated = true; break end
            end
            table.sort(keys, function(a, b) return a.text < b.text end)
            for _, item in ipairs(keys) do emit("api." .. name .. "." .. item.text, item.kind) end
        end
        return value
    end
    emit("report.kind", "runtime_metadata_only_not_a_gameplay_test")
    emit("report.schema", "1")
    emit("runtime.lua", _VERSION)
    for _, name in ipairs({"Dynamite", "TppQuest", "TppQuestList", "TppSequence", "TppMission",
            "TppLocation", "TppNetworkUtil", "TppGameStatus", "TppScriptVars", "TppCheckPoint",
            "TppEnemy", "TppPlayer", "TppStory", "TppSave", "ScriptBlock", "Mission", "PlayerInfo"}) do
        module(name)
    end
    for _, item in ipairs({{"vars", "missionCode"}, {"vars", "locationCode"},
            {"mvars", "mis_missionName"}, {"mvars", "seq_currentSequence"}, {"svars", "seq_sequence"}}) do
        local value, kind = field(rawget(_G, item[1]), item[2])
        emit("state." .. item[1] .. "." .. item[2] .. ".type", kind)
        emit("state." .. item[1] .. "." .. item[2], scalar(value))
    end
    for _, query in ipairs({{"Dynamite", "IsHost"}, {"Dynamite", "IsClient"},
            {"TppNetworkUtil", "IsHost"}, {"TppNetworkUtil", "IsSessionConnect"},
            {"TppGameStatus", "IsSet", "Mission", "S_IS_ONLINE"}}) do
        local api = rawget(_G, query[1])
        local func = type(api) == "table" and rawget(api, query[2]) or nil
        local ok, value = false, nil
        if type(func) == "function" then
            if query[3] then ok, value = pcall(func, query[3], query[4])
            else ok, value = pcall(func) end
        end
        emit("query." .. query[1] .. "." .. query[2], ok and scalar(value) or "<unavailable>")
    end
    local quests = rawget(_G, "TppQuestList") or rawget(package.loaded, "TppQuestList")
    if type(quests) == "table" then
        walk("quests.questList", rawget(quests, "questList"), 0)
        walk("quests.questPackList", rawget(quests, "questPackList"), 0)
    else emit("quests", "<module not loaded>") end
    local mvars = rawget(_G, "mvars")
    if type(mvars) == "table" then
        local count, scanned = 0, 0
        for key, value in next, mvars do
            scanned = scanned + 1
            if scanned > maxEntries then truncated = true; break end
            local name = safeKey(key)
            if name and name:match("^qst_") then
                emit("quest_runtime_shape." .. name, type(value))
                count = count + 1
                if count >= maxEntries then truncated = true; break end
            end
        end
    end
    lines[#lines + 1] = "report.truncated\t" .. tostring(truncated) .. "\n"
    lines[#lines + 1] = "report.complete\ttrue\n"
    return table.concat(lines)
end

function inventory.Probe()
    notify("WW inventory: binding works")
    return true
end

function inventory.Collect()
    notify("WW inventory: collector started")
    local api = rawget(_G, "Dynamite")
    local log = type(api) == "table" and rawget(api, "Log") or nil
    if type(log) ~= "function" then
        notify("WW inventory: native log API unavailable"); return false
    end
    local ok, report = pcall(makeReport)
    if not ok then notify("WW inventory: collection failed"); return false end
    -- Adler-32 needs no bit library and fits exactly in Lua 5.1's number type.
    local a, b = 1, 0
    for i = 1, #report do
        a = (a + report:byte(i)) % 65521
        b = (b + a) % 65521
    end
    local checksum = string.format("%.0f", b * 65536 + a)
    serial = serial + 1
    local id = string.format("%.0f", os.time()) .. "-" .. serial
    local chunkBytes = 384
    local chunks = math.ceil(#report / chunkBytes)
    local header = id .. " " .. #report .. " " .. chunks .. " " .. checksum
    local function send(message)
        return pcall(log, "[WWINV1] " .. message)
    end
    if not send("BEGIN " .. header) then
        notify("WW inventory: native log export failed"); return false
    end
    for index = 1, chunks do
        local chunk = report:sub((index - 1) * chunkBytes + 1, index * chunkBytes)
        local hex = chunk:gsub(".", function(char) return string.format("%02x", char:byte()) end)
        if not send("DATA " .. id .. " " .. index .. " " .. hex) then
            notify("WW inventory: native log export failed"); return false
        end
    end
    if not send("END " .. header) then
        notify("WW inventory: native log export failed"); return false
    end
    -- Log returns no persistence result. The extractor verifies the actual bytes.
    notify("WW inventory: report sent to Dynamite log")
    return true, id
end

return inventory
