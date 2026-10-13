from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, AwareDatetime


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Tariff(Model):
    start: AwareDatetime
    end: AwareDatetime
    price_per_kwh: Decimal


class Device(Model):
    device_id: str = "ev-1"
    name: str = "Driveway EV · simulated"
    simulated: Literal[True] = True
    required_kwh: Decimal = Field(default=Decimal("21"), gt=0)
    max_power_kw: Decimal = Field(default=Decimal("7"), gt=0)
    available_from: AwareDatetime
    available_until: AwareDatetime
    revision: int = 0
    active_plan_id: str | None = None


class Slot(Model):
    start: AwareDatetime
    end: AwareDatetime
    energy_kwh: Decimal
    power_kw: Decimal
    price_per_kwh: Decimal
    cost: Decimal


class Schedule(Model):
    slots: list[Slot]
    energy_kwh: Decimal
    cost: Decimal


class Proposal(Model):
    plan_id: str
    device_id: str
    device_revision: int
    deadline: AwareDatetime
    optimized: Schedule
    baseline: Schedule
    savings: Decimal
    savings_percent: Decimal
    currency: Literal["INR"] = "INR"
    status: Literal["awaiting_confirmation"] = "awaiting_confirmation"
    dataset: str = "synthetic-demo-v1"


class Prices(Model):
    dataset: str
    synthetic: Literal[True]
    currency: Literal["INR"]
    tariffs: list[Tariff]


class Execution(Model):
    execution_id: str
    plan_id: str
    status: Literal["scheduled"]
    simulated: Literal[True]
    confirmed: Literal[True]
    executed_at: AwareDatetime
    demo_clock: AwareDatetime
    proposal: Proposal


class History(Model):
    executions: list[Execution]


T = TypeVar("T")


class Result(Model, Generic[T]):
    ok: bool
    code: str
    message: str
    data: T | None = None


class DomainError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
