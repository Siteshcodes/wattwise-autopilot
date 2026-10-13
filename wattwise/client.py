"""All simulator and gateway tool calls cross the real MCP HTTP transport."""
import os
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .models import DomainError, Result


@asynccontextmanager
async def connection(url=None):
    try:
        async with streamable_http_client(url or os.getenv("WATTWISE_MCP_URL", "http://127.0.0.1:8000/mcp")) as (read, write, _):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                if initialized.protocolVersion != "2025-11-25":
                    raise RuntimeError(f"Unexpected MCP protocol: {initialized.protocolVersion}")
                yield session
    except BaseExceptionGroup as group:
        # anyio task groups wrap application errors; retain actionable domain explanations.
        def find_domain(exc):
            if isinstance(exc, DomainError):
                return exc
            if isinstance(exc, BaseExceptionGroup):
                for child in exc.exceptions:
                    found = find_domain(child)
                    if found:
                        return found
            return None
        domain = find_domain(group)
        if domain:
            raise domain from group
        raise


async def call(session, name, arguments=None):
    response = await session.call_tool(name, arguments or {})
    if response.isError:
        raise DomainError("MCP_TOOL_ERROR", str(response.content))
    result = Result[dict].model_validate(response.structuredContent)
    if not result.ok:
        raise DomainError(result.code, result.message)
    return result.data
