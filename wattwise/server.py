import os
import sqlite3
from typing import Annotated

from fastmcp import FastMCP
from pydantic import AwareDatetime, Field, StrictBool

from .models import Device, DomainError, Execution, History, Prices, Proposal, Result
from .store import Store

mcp = FastMCP("WattWise · simulated home energy")


def invoke(fn, result_type):
    try:
        return result_type(ok=True, code="OK", message="Success", data=fn())
    except DomainError as exc:
        return result_type(ok=False, code=exc.code, message=str(exc))
    except sqlite3.Error:
        return result_type(ok=False, code="STORAGE_ERROR", message="SQLite operation failed; no successful action is implied.")


@mcp.tool(annotations={"readOnlyHint": True})
def get_energy_prices() -> Result[Prices]:
    """Read seeded synthetic hourly electricity prices; these are not live tariffs."""
    return invoke(lambda: {"dataset": "synthetic-demo-v1", "synthetic": True, "currency": "INR", "tariffs": Store().prices()}, Result[Prices])


@mcp.tool(annotations={"readOnlyHint": True})
def get_device_constraints(device_id: str = "ev-1") -> Result[Device]:
    """Read persistent constraints and active schedule of a simulated EV charger."""
    return invoke(lambda: Store().device(device_id), Result[Device])


@mcp.tool()
def optimize_schedule(deadline: AwareDatetime, device_id: str = "ev-1") -> Result[Proposal]:
    """Compute and persist a proposal and immediate-at-maximum-power baseline; never apply it."""
    return invoke(lambda: Store().optimize(device_id, deadline), Result[Proposal])


@mcp.tool(annotations={"destructiveHint": True, "idempotentHint": True})
def apply_schedule(plan_id: str, confirmed: StrictBool) -> Result[Execution]:
    """Apply a stored proposal ONLY after the human explicitly approves this exact plan. Never infer consent."""
    return invoke(lambda: Store().apply(plan_id, confirmed), Result[Execution])


@mcp.tool(annotations={"readOnlyHint": True})
def get_execution_history(limit: Annotated[int, Field(ge=1, le=100)] = 20) -> Result[History]:
    """Read the persisted confirmation, applied action, both schedules and calculations."""
    return invoke(lambda: {"executions": Store().history(limit)}, Result[History])


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=int(os.getenv("WATTWISE_MCP_PORT", "8000")))
