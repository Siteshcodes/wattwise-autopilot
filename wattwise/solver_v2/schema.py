from datetime import datetime
from enum import StrEnum
from math import exp
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Tier(StrEnum):
    STATED = "stated"
    FIRM = "firm"


class EV(Model):
    required_battery_energy_kwh: float = Field(gt=0)
    power_levels_kw: list[float] = Field(min_length=2)
    efficiency: float = Field(gt=0, le=1)
    available_from_slot: StrictInt = Field(ge=0)
    deadline_slot: StrictInt = Field(ge=0)
    deadline_tier: Tier = Tier.STATED

    @model_validator(mode="after")
    def levels(self):
        if self.power_levels_kw != sorted(set(self.power_levels_kw)) or self.power_levels_kw[0] != 0:
            raise ValueError("EV levels must be finite, distinct, increasing, and start with zero")
        return self


class Washer(Model):
    power_kw: float = Field(gt=0)
    duration_slots: StrictInt = Field(ge=1)
    earliest_start_slot: StrictInt = Field(ge=0)
    must_finish_by_slot: StrictInt = Field(ge=0)
    deadline_tier: Tier = Tier.STATED


class HVAC(Model):
    power_kw: float = Field(gt=0)
    initial_temp_c: float
    min_temp_c: float
    max_temp_c: float
    comfort_tier: Literal["protected"] = "protected"
    tau_hours: float = Field(gt=0, description="Thermal RC time constant, hours")
    cooling_per_slot_c: float = Field(gt=0, description="Temperature reduction per ON slot, degrees C; includes COP")
    cooling_cop: float = Field(default=3, gt=0)
    coefficient_source: str = "constructed example; not calibrated to a real building"
    min_on_slots: StrictInt = Field(default=2, ge=1)
    min_off_slots: StrictInt = Field(default=2, ge=1)
    initial_on: Literal[0, 1] = 0
    initial_state_elapsed_slots: StrictInt = Field(default=2, ge=0)
    terminal_policy: Literal["complete_within_horizon"] = "complete_within_horizon"

    @model_validator(mode="after")
    def band(self):
        if self.min_temp_c >= self.max_temp_c:
            raise ValueError("Comfort lower bound must be below upper bound")
        return self


class Request(Model):
    request_id: str
    horizon_start: datetime
    slot_minutes: Literal[15] = 15
    panel_limit_kw: float = Field(default=9.6, gt=0)
    tariff_dataset_id: str
    tariff_usd_per_kwh: list[float] = Field(min_length=1, max_length=96)
    base_load_kw: list[float]
    outdoor_temp_c: list[float]
    ev: EV
    washer: Washer
    hvac: HVAC
    budget_usd: float = Field(ge=0)
    budget_scope: Literal["total_home", "controllable"]
    budget_tier: Tier = Tier.STATED
    preference_scope: Literal["standing", "tomorrow_only"] = "standing"
    negotiable: list[Literal["budget", "washer_deadline", "ev_deadline"]] = Field(default_factory=list)

    @property
    def n(self):
        return len(self.tariff_usd_per_kwh)

    @property
    def dt(self):
        return self.slot_minutes / 60

    @property
    def a(self):
        return exp(-self.dt / self.hvac.tau_hours)

    @model_validator(mode="after")
    def validate_instance(self):
        if len(self.base_load_kw) != self.n or len(self.outdoor_temp_c) != self.n + 1:
            raise ValueError("Require N tariffs, N base loads, and N+1 outdoor boundary temperatures")
        if any(x < 0 for x in self.base_load_kw):
            raise ValueError("Base loads must be nonnegative")
        if any(x <= self.hvac.min_temp_c for x in self.outdoor_temp_c):
            raise ValueError("Cooling-only model requires every outdoor temperature > T_min; add heating otherwise")
        if self.horizon_start.hour != 18 or any((self.horizon_start.minute, self.horizon_start.second, self.horizon_start.microsecond)):
            raise ValueError("Horizon starts at local 18:00")
        if any(x > self.n for x in (self.ev.available_from_slot, self.ev.deadline_slot, self.washer.earliest_start_slot, self.washer.must_finish_by_slot, self.washer.duration_slots)):
            raise ValueError("Device windows and washer duration must be within the horizon")
        if len(set(self.negotiable)) != len(self.negotiable):
            raise ValueError("Negotiable dimensions must be unique")
        return self


class Options(Model):
    time_limit_s: float = Field(default=2, ge=0, le=2)
    feasibility_tolerance: float = Field(default=1e-6, gt=0, le=1e-5)
    cost_tolerance_usd: float = Field(default=1e-7, gt=0, le=1e-5)
    seed: int = Field(default=0,ge=0,le=2147483647)
    max_extensions: int = Field(default=4, ge=1, le=24)
    workers: int = Field(default=4, ge=1, le=4)


class Schedule(Model):
    ev_power_kw: list[float]
    washer_on: list[int]
    washer_start_slot: int
    hvac_on: list[int]
    hvac_startup: list[int]
    hvac_shutdown: list[int]
    temperature_c: list[float]
    total_load_kw: list[float]
    slot_starts: list[str]
    ev_completion_slot: int
    ev_battery_energy_kwh: float
    ev_grid_energy_kwh: float
    hvac_switches: int
    cost_usd: float


class ConstraintCheck(Model):
    key: str
    tier: Literal["physical", "protected"]
    satisfied: bool
    min_slack: float
    slacks: list[float]
    units: str


class Evidence(Model):
    stage: str
    solver_status: str
    proven_optimal: bool
    incumbent_objective: float | None = None
    lower_bound: float | None = None
    gap: float | None = None
    objective_units: str
    time_limit_s: float


class SolveResult(Model):
    status: Literal["OPTIMAL", "INFEASIBLE_PHYSICAL", "TIME_LIMIT", "ERROR"]
    min_cost_usd: float | None = None
    lower_bound_usd: float | None = None
    gap: float | None = None
    schedule: Schedule | None = None
    constraint_report: list[ConstraintCheck] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    lexicographic_complete: bool = False
    message: str = ""


class Response(Model):
    status: Literal["OPTIMAL_WITHIN_BUDGET", "BUDGET_MISS", "INFEASIBLE_PHYSICAL", "TIME_LIMIT", "ERROR"]
    min_cost_usd: float | None = None
    lower_bound_usd: float | None = None
    gap: float | None = None
    schedule: Schedule | None = None
    constraint_report: list[ConstraintCheck] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    counteroffers: list[dict] = Field(default_factory=list)
    cost_curves: dict[str, list[dict]] = Field(default_factory=dict)
    diagnostics: list[dict] = Field(default_factory=list)
    cost_driving: list[dict] = Field(default_factory=list)
    persist: dict = Field(default_factory=lambda: {"decisions": [], "preference_updates": []})
    thermal_coefficients: dict = Field(default_factory=dict)
    input_hash: str = ""
    output_hash: str = ""
    lexicographic_complete: bool = False
    message: str = ""
