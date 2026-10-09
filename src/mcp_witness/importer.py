"""Extract MCP tools/call requests; unknown request formats never silently pass."""

from __future__ import annotations

from mcp_witness.data import InputError, cases, parse_json


def import_calls(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        raise InputError("Trace is empty")
    try:
        value = parse_json(stripped)
    except InputError:
        # Each nonempty JSONL line must be valid; do not skip damaged records.
        messages = [parse_json(line) for line in stripped.splitlines() if line.strip()]
    else:
        messages = value if isinstance(value, list) else [value]
    output = []
    for index, message in enumerate(messages, 1):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise InputError("Trace records must be MCP JSON-RPC 2.0 objects")
        if "method" in message:
            if not isinstance(message["method"], str) or not message["method"]:
                raise InputError("JSON-RPC method must be a nonempty string")
            if "result" in message or "error" in message:
                raise InputError("JSON-RPC requests cannot contain response fields")
            if "params" in message and not isinstance(message["params"], dict):
                raise InputError("MCP request params must be an object")
        elif "id" not in message or ("result" in message) == ("error" in message):
            raise InputError("Malformed JSON-RPC response record")
        if message.get("method") != "tools/call":
            continue
        params = message.get("params")
        if not isinstance(params, dict):
            raise InputError("tools/call request is missing params")
        if (
            "id" not in message
            or isinstance(message["id"], bool)
            or not isinstance(message["id"], (int, str))
        ):
            raise InputError("tools/call must have a string or integer request id")
        output.append(
            {
                "id": f"call-{index:04d}",
                "tool": params.get("name"),
                "arguments": params.get("arguments", {}),
            }
        )
    result = {"cases": output}
    cases(result)
    return result
