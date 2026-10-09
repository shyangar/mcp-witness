"""Optional MCP SDK transport: initialize + tools/list only, never tools/call."""

from __future__ import annotations

import tempfile

from mcp_witness.data import MAX_TOOLS, InputError, catalog


async def capture(command: list[str], timeout: float = 30) -> dict:
    try:
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise InputError("Capture requires the optional extra: pip install '.[capture]'") from exc
    if not command:
        raise InputError("Provide a server command after --")
    tools: list[dict] = []
    cursors: set[str] = set()
    try:
        # Keep stderr out of reports: servers may log credentials or other private data.
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
            with anyio.fail_after(timeout):
                parameters = StdioServerParameters(command=command[0], args=command[1:])
                async with stdio_client(parameters, errlog=stderr) as streams:
                    async with ClientSession(*streams) as session:
                        initialized = await session.initialize()
                        if initialized.capabilities.tools is None:
                            raise InputError("Server did not declare tools capability")
                        cursor = None
                        for _ in range(100):
                            page = await session.list_tools(cursor=cursor)
                            tools.extend(
                                tool.model_dump(mode="json", exclude_none=True)
                                for tool in page.tools
                            )
                            if len(tools) > MAX_TOOLS:
                                raise InputError("Server exceeds the 2000 tool limit")
                            cursor = page.nextCursor
                            if cursor is None:
                                return catalog({"tools": tools})
                            if cursor in cursors:
                                raise InputError("Server repeated a pagination cursor")
                            cursors.add(cursor)
                        raise InputError("Server exceeds the 100 page limit")
    except TimeoutError as exc:
        raise InputError("Server discovery timed out; no snapshot was written") from exc
    except InputError:
        raise
    except Exception as exc:
        raise InputError(
            "MCP discovery failed; check command, capabilities and protocol locally"
        ) from exc
