"""Independent replay validator: does not inspect MILP rows or solver variables."""
from datetime import timedelta
from math import fsum

from .schema import ConstraintCheck, Request, Schedule


def replay(request: Request, ev: list[float], washer_start: int, hvac: list[int]) -> Schedule:
    n, h = request.n, request.hvac
    washer = [int(washer_start <= t < washer_start + request.washer.duration_slots) for t in range(n)]
    temps = [h.initial_temp_c]
    starts, stops = [], []
    previous = h.initial_on
    for t, state in enumerate(hvac):
        starts.append(int(state == 1 and previous == 0))
        stops.append(int(state == 0 and previous == 1))
        previous = state
        temps.append(request.a * temps[-1] + (1-request.a) * request.outdoor_temp_c[t] - h.cooling_per_slot_c * state)
    loads = [fsum((request.base_load_kw[t], ev[t], request.washer.power_kw * washer[t], h.power_kw * hvac[t])) for t in range(n)]
    modeled = loads if request.budget_scope == "total_home" else [loads[t]-request.base_load_kw[t] for t in range(n)]
    return Schedule(
        ev_power_kw=ev, washer_on=washer, washer_start_slot=washer_start,
        hvac_on=hvac, hvac_startup=starts, hvac_shutdown=stops,
        temperature_c=temps, total_load_kw=loads,
        slot_starts=[(request.horizon_start+timedelta(minutes=15*t)).isoformat() for t in range(n)],
        ev_completion_slot=max((t+1 for t,p in enumerate(ev) if p > 0), default=0),
        ev_grid_energy_kwh=request.dt*fsum(ev), ev_battery_energy_kwh=request.ev.efficiency*request.dt*fsum(ev),
        hvac_switches=sum(starts)+sum(stops),
        cost_usd=fsum(request.dt*c*p for c,p in zip(request.tariff_usd_per_kwh,modeled)),
    )


def verify(request: Request, plan: Schedule, tolerance=1e-6) -> list[ConstraintCheck]:
    n, h, checks = request.n, request.hvac, []

    def check(key, slacks, units, protected=False):
        values = list(slacks)
        checks.append(ConstraintCheck(key=key, tier="protected" if protected else "physical", satisfied=min(values,default=0) >= -tolerance, min_slack=min(values,default=0), slacks=values, units=units))

    arrays = (plan.ev_power_kw, plan.washer_on, plan.hvac_on, plan.hvac_startup, plan.hvac_shutdown, plan.total_load_kw, plan.slot_starts)
    if any(len(x) != n for x in arrays) or len(plan.temperature_c) != n+1:
        check("shape", [-1], "slots")
        return checks
    check("C1.ev_discrete_levels", [-min(abs(p-k) for k in request.ev.power_levels_kw) for p in plan.ev_power_kw], "kW")
    check("C2.ev_window", [-abs(plan.ev_power_kw[t]) for t in range(n) if t < request.ev.available_from_slot or t >= request.ev.deadline_slot], "kW")
    check("C3.ev_battery_energy", [request.ev.efficiency*request.dt*fsum(plan.ev_power_kw)-request.ev.required_battery_energy_kwh], "kWh")
    expected = replay(request, plan.ev_power_kw, plan.washer_start_slot, plan.hvac_on)
    w = request.washer
    check("C4.washer_window", [plan.washer_start_slot-w.earliest_start_slot, w.must_finish_by_slot-plan.washer_start_slot-w.duration_slots], "slots")
    check("C4.washer_uninterrupted", [-abs(a-b) for a,b in zip(plan.washer_on,expected.washer_on)] + [-abs(sum(plan.washer_on)-w.duration_slots)], "slots")
    check("C5.hvac_binary", [-min(abs(x),abs(x-1)) for x in plan.hvac_on], "binary")
    check("C5.hvac_startup_shutdown", [-abs(a-b) for a,b in zip(plan.hvac_startup,expected.hvac_startup)] + [-abs(a-b) for a,b in zip(plan.hvac_shutdown,expected.hvac_shutdown)], "binary")
    duration_slacks=[]
    initial_min = h.min_on_slots if h.initial_on else h.min_off_slots
    remaining = max(0, initial_min-h.initial_state_elapsed_slots)
    duration_slacks.extend(-abs(plan.hvac_on[t]-h.initial_on) for t in range(min(n,remaining)))
    for t in range(n):
        if expected.hvac_startup[t] or expected.hvac_shutdown[t]:
            state = plan.hvac_on[t]
            duration = h.min_on_slots if state else h.min_off_slots
            duration_slacks.append(n-t-duration)  # no truncated terminal runs
            duration_slacks.extend(-abs(plan.hvac_on[u]-state) for u in range(t,min(n,t+duration)))
    check("C5.hvac_min_durations_and_boundaries", duration_slacks, "slots")
    check("C6.initial_temperature", [-abs(plan.temperature_c[0]-h.initial_temp_c)], "C")
    check("C6.thermal_dynamics", [-abs(plan.temperature_c[t+1]-(request.a*plan.temperature_c[t]+(1-request.a)*request.outdoor_temp_c[t]-h.cooling_per_slot_c*plan.hvac_on[t])) for t in range(n)], "C")
    check("C7.panel_including_base", [request.panel_limit_kw-p for p in expected.total_load_kw], "kW")
    check("C8.comfort_lower", [v-h.min_temp_c for v in plan.temperature_c], "C", True)
    check("C8.comfort_upper", [h.max_temp_c-v for v in plan.temperature_c], "C", True)
    check("reported_load", [-abs(a-b) for a,b in zip(plan.total_load_kw,expected.total_load_kw)], "kW")
    check("reported_cost", [-abs(plan.cost_usd-expected.cost_usd)], "USD")
    check("reported_energy", [-abs(plan.ev_battery_energy_kwh-expected.ev_battery_energy_kwh),-abs(plan.ev_grid_energy_kwh-expected.ev_grid_energy_kwh)], "kWh")
    check("reported_switches_completion", [-abs(plan.hvac_switches-expected.hvac_switches),-abs(plan.ev_completion_slot-expected.ev_completion_slot)], "slots")
    check("reported_slot_starts", [0 if plan.slot_starts==expected.slot_starts else -1], "timestamps")
    return checks
