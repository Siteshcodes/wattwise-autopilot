import httpx

from wattwise.api import app, approvals


async def test_dashboard_flow_through_real_mcp(server, monkeypatch):
    monkeypatch.setenv("WATTWISE_MCP_URL",server[0])
    monkeypatch.setenv("WATTWISE_PROVIDER","deterministic")
    approvals.clear()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        assert (await client.get("/api/state")).json()["history"]["executions"] == []
        bad = await client.post("/api/plan",json={"text":"Charge my EV before 9 PM"})
        assert bad.status_code == 400
        assert bad.json()["detail"]["code"] == "INFEASIBLE"
        response = await client.post("/api/plan",json={"text":"Charge my EV before 7 AM using the cheapest available electricity."})
        assert response.status_code == 200
        reviewed = response.json()
        body = {"plan_id":reviewed["proposal"]["plan_id"],"confirmation_token":reviewed["confirmation_token"],"confirmed":True}
        assert (await client.post("/api/approve",json={**body,"confirmed":False})).status_code == 403
        assert (await client.post("/api/approve",json={**body,"confirmation_token":"wrong"})).status_code == 403
        assert (await client.get("/api/state")).json()["device"]["active_plan_id"] is None
        assert (await client.post("/api/approve",json=body)).status_code == 200
        assert (await client.post("/api/approve",json=body)).status_code == 200
        final = (await client.get("/api/state")).json()
        assert len(final["history"]["executions"]) == 1
        assert final["device"]["active_plan_id"] == body["plan_id"]
