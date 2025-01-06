-- postresolve runs after the packet has been answered, and can be used to change things
-- or still drop
local websocket = require "http.websocket"
local cjson = require("cjson")
local ipt_ws = os.getenv("IPT_WS")
local ws_uri = "ws://127.0.0.1:8765"
if ipt_ws ~= nil then
    ws_uri = "ws://" .. ipt_ws
end
local ws = websocket.new_from_uri(ws_uri)
ws:connect()

function postresolve(dq)
    pdnslog("postresolve called for " .. dq.qname:toString())
    local records = dq:getRecords()
    for k, v in pairs(records) do
        pdnslog(k .. " " .. v.name:toString() .. " " .. v:getContent() .. " " .. v.type, pdns.loglevels.Debug)
        local message = {
            query = dq.qname:toString(),
            name = v.name:toString(),
            type = v.type,
            content = v:getContent()
        }
        --        if string.len(message) > 0 then
        local json_message = cjson.encode(message)
        pdnslog(json_message, pdns.loglevels.Debug)
        if v.type == pdns.A then
            if not ws:send(json_message) then
                pdnslog('Reconnecting ipt-server')
                ws = nil
                ws = websocket.new_from_uri(ws_uri)
                ws:connect()
                ws:send(json_message)
            end
            ws:receive()
        end
    end
    dq:setRecords(records)
    return true
end
function maintenance()
    -- to handle keepalive ping/pong
    local x = ws:receive(0)
    if not x == nil then
        pdnslog(x)
    end
end