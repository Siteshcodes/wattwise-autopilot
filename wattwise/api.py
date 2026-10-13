"""Local dashboard gateway. Scheduling operations always use MCP over HTTP."""
import asyncio
import secrets

from fastapi import FastAPI, HTTPException
from pydantic import Field, StrictBool

from .client import call, connection
from .models import DomainError, Model
from .providers import provider
from .store import demo_now

app = FastAPI(title="WattWise local simulator gateway")
# Capabilities belong only to reviewed dashboard proposals. Restart requires a new review.
approvals: dict[str, str] = {}


class Request(Model):
    text: str = Field(min_length=1, max_length=1000)


class Approval(Model):
    plan_id: str
    confirmation_token: str
    confirmed: StrictBool


async def guarded(fn):
    try:
        return await fn()
    except DomainError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    except Exception as exc:
        # ExceptionGroups can be raised by the SDK task groups on connection failure.
        raise HTTPException(status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "message": "MCP or provider unavailable. Check the backend logs; no successful action is implied."}) from exc


@app.get("/api/state")
async def state():
    async def run():
        async with connection() as session:
            return {"device": await call(session, "get_device_constraints"), "prices": await call(session, "get_energy_prices"), "history": await call(session, "get_execution_history"), "demo_now": demo_now().isoformat()}
    return await guarded(run)


@app.post("/api/plan")
async def plan(request: Request):
    async def run():
        intent = await asyncio.to_thread(lambda: provider().parse(request.text, demo_now()))
        async with connection() as session:
            # Explicitly retrieve the inputs before optimization; the server reloads authoritative data.
            await call(session, "get_energy_prices")
            await call(session, "get_device_constraints")
            result = await call(session, "optimize_schedule", {"deadline": intent.deadline.isoformat()})
        token = secrets.token_urlsafe(32)
        approvals[result["plan_id"]] = token
        return {"proposal": result, "confirmation_token": token}
    return await guarded(run)


@app.post("/api/approve")
async def approve(request: Approval):
    expected = approvals.get(request.plan_id)
    if request.confirmed is not True or expected is None or not secrets.compare_digest(expected, request.confirmation_token):
        raise HTTPException(status_code=403, detail={"code": "CONFIRMATION_REQUIRED", "message": "Review this proposal and explicitly confirm it first."})
    async def run():
        async with connection() as session:
            return await call(session, "apply_schedule", {"plan_id": request.plan_id, "confirmed": True})
    return await guarded(run)
