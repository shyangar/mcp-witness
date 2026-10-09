"""A protocol fixture that rejects tools/call and can simulate bad transports."""

import json
import sys
import time

mode = sys.argv[1]
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        if mode == "timeout":
            time.sleep(60)
        if mode == "crash":
            print("PRIVATE_SERVER_STDERR", file=sys.stderr)
            sys.exit(1)
        result = {
            "protocolVersion": message["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "protocol-fixture", "version": "1"},
        }
    elif method == "tools/list":
        cursor = message.get("params", {}).get("cursor")
        result = {
            "tools": [{"name": "second" if cursor else "first", "inputSchema": {"type": "object"}}]
        }
        if cursor is None or mode == "repeated-cursor":
            result["nextCursor"] = "page-2"
    elif method == "tools/call":
        raise RuntimeError("Discovery must never execute a tool")
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
