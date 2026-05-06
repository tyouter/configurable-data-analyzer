import requests, json

BASE = "http://localhost:8765/mcp"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
_sid = None
_rid = 0

def call(method, params=None):
    global _sid, _rid
    _rid += 1
    h = dict(HEADERS)
    if _sid:
        h["mcp-session-id"] = _sid
    r = requests.post(BASE, json={"jsonrpc": "2.0", "id": _rid, "method": method, "params": params or {}}, headers=h, timeout=60)
    sid = r.headers.get("mcp-session-id")
    if sid:
        _sid = sid
    ct = r.headers.get("content-type", "")
    if "text/event-stream" in ct:
        for line in r.text.split("\n"):
            if line.startswith("data: "):
                try:
                    return json.loads(line[6:])
                except:
                    pass
    elif "application/json" in ct:
        return r.json()
    return None

def tool(name, args=None):
    return call("tools/call", {"name": name, "arguments": args or {}})

def text(r):
    if not r:
        return ""
    c = r.get("result", {}).get("content", [])
    return "\n".join(x.get("text", "") for x in c if x.get("type") == "text")

call("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1.0"}})
tool("switch_project", {"project_id": "828eb486"})

r = tool("raw_sql", {"sql": "SELECT column_name FROM (DESCRIBE events) WHERE column_name LIKE '%time%' OR column_name LIKE '%start%'"})
print("Time columns:", text(r)[:300])

r = tool("raw_sql", {"sql": "SELECT start_time_nano FROM events LIMIT 2"})
print("start_time_nano sample:", text(r)[:300])

r = tool("raw_sql", {"sql": "DESCRIBE events"})
print("All columns:", text(r)[:1000])
