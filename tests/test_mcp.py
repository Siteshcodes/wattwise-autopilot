import sqlite3

import httpx
import pytest

from wattwise.client import call, connection


async def test_real_http_protocol_and_all_tools(server):
    url, db_path = server
    async with connection(url) as session:
        listing = await session.list_tools()
        assert {t.name for t in listing.tools} == {"get_energy_prices", "get_device_constraints", "optimize_schedule", "apply_schedule", "get_execution_history"}
        assert all(t.inputSchema and t.outputSchema for t in listing.tools)
        assert (await call(session,"get_energy_prices"))["synthetic"] is True
        assert (await call(session,"get_device_constraints"))["active_plan_id"] is None
        assert (await call(session,"get_execution_history"))["executions"] == []
        plan = await call(session,"optimize_schedule", {"deadline":"2026-10-13T07:00:00+05:30"})
        assert float(plan["savings"]) == 168
        second = await call(session,"optimize_schedule", {"deadline":"2026-10-13T07:00:00+05:30"})
        rejected = await session.call_tool("apply_schedule", {"plan_id":plan["plan_id"],"confirmed":False})
        assert rejected.structuredContent["code"] == "CONFIRMATION_REQUIRED"
        assert (await call(session,"get_device_constraints"))["active_plan_id"] is None
        action = await call(session,"apply_schedule", {"plan_id":plan["plan_id"],"confirmed":True})
        assert action["status"] == "scheduled"
        repeat = await call(session,"apply_schedule", {"plan_id":plan["plan_id"],"confirmed":True})
        assert action == repeat
        stale = await session.call_tool("apply_schedule", {"plan_id":second["plan_id"],"confirmed":True})
        assert stale.structuredContent["code"] == "STALE_PLAN"
    # A fresh transport session sees persisted state, and SQLite holds the full calculations.
    async with connection(url) as session:
        history = (await call(session,"get_execution_history"))["executions"]
        assert len(history) == 1
        assert history[0]["proposal"] == plan
        assert (await call(session,"get_device_constraints"))["active_plan_id"] == plan["plan_id"]
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM executions").fetchone()[0] == 1


async def test_tool_validation_and_errors(server):
    async with connection(server[0]) as session:
        for name,args,code in [
            ("get_device_constraints", {"device_id":"missing"}, "UNKNOWN_DEVICE"),
            ("apply_schedule", {"plan_id":"missing","confirmed":True}, "UNKNOWN_PLAN"),
            ("optimize_schedule", {"deadline":"2026-10-12T21:00:00+05:30"}, "INFEASIBLE"),
        ]:
            result = await session.call_tool(name,args)
            assert result.structuredContent["ok"] is False
            assert result.structuredContent["code"] == code
        for name,args in [
            ("optimize_schedule", {"deadline":"2026-10-13T07:00:00"}),
            ("apply_schedule", {"plan_id":"x","confirmed":"true"}),
            ("get_execution_history", {"limit":0}),
        ]:
            assert (await session.call_tool(name,args)).isError


def test_wire_initialize_2025_11_25(server):
    response = httpx.post(server[0], headers={"Accept":"application/json, text/event-stream"}, json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"wattwise-wire-test","version":"1"}}})
    assert response.status_code == 200
    assert '"protocolVersion":"2025-11-25"' in response.text
    assert "mcp-session-id" in response.headers
