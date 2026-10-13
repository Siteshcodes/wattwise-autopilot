"""Exhaustive discrete verifier for <=8 slots. No MILP/model-builder dependency."""
from itertools import product
from math import exp, fsum

from .schema import Request
from .verify import replay


def brute_force(request: Request, tolerance=1e-6):
    if request.n > 8:
        raise ValueError("Brute-force verification is limited to at most 8 slots")
    r, n, h = request, request.n, request.hvac
    best, best_choices, considered = None, None, 0
    a = exp(-(r.slot_minutes/60)/h.tau_hours)
    valid_hvac=[]
    for states in product((0,1),repeat=n):
        previous, elapsed, temp, valid, switches = h.initial_on, h.initial_state_elapsed_slots, h.initial_temp_c, True, 0
        if temp < h.min_temp_c-tolerance or temp > h.max_temp_c+tolerance:
            continue
        for t,state in enumerate(states):
            if state != previous:
                if elapsed < (h.min_on_slots if previous else h.min_off_slots):
                    valid=False
                    break
                if n-t < (h.min_on_slots if state else h.min_off_slots):
                    valid=False
                    break
                elapsed, switches = 0, switches+1
            elapsed += 1
            previous = state
            temp = a*temp+(1-a)*r.outdoor_temp_c[t]-h.cooling_per_slot_c*state
            if temp < h.min_temp_c-tolerance or temp > h.max_temp_c+tolerance:
                valid=False
                break
        if valid:
            valid_hvac.append((states,switches))
    levels = [r.ev.power_levels_kw if r.ev.available_from_slot <= t < r.ev.deadline_slot else [0] for t in range(n)]
    for powers in product(*levels):
        if r.ev.efficiency*(r.slot_minutes/60)*fsum(powers) < r.ev.required_battery_energy_kwh-tolerance:
            continue
        completion=max((t+1 for t,p in enumerate(powers) if p>0),default=0)
        for start in range(r.washer.earliest_start_slot,r.washer.must_finish_by_slot-r.washer.duration_slots+1):
            washer=[int(start <= t < start+r.washer.duration_slots) for t in range(n)]
            for states,switches in valid_hvac:
                loads=[r.base_load_kw[t]+powers[t]+r.washer.power_kw*washer[t]+h.power_kw*states[t] for t in range(n)]
                considered+=1
                if any(load > r.panel_limit_kw+tolerance for load in loads):
                    continue
                cost=fsum(r.tariff_usd_per_kwh[t]*(r.slot_minutes/60)*(loads[t] if r.budget_scope == "total_home" else loads[t]-r.base_load_kw[t]) for t in range(n))
                key=(cost,switches,completion)
                if best is None or cost < best[0]-1e-7 or (abs(cost-best[0]) <= 1e-7 and key[1:] < best[1:]):
                    best,best_choices=key,(list(powers),start,list(states))
    if best is None:
        return {"status":"INFEASIBLE_PHYSICAL","cost_usd":None,"schedule":None,"enumerated_combinations":considered}
    return {"status":"OPTIMAL","cost_usd":best[0],"schedule":replay(r,*best_choices),"hvac_switches":best[1],"ev_completion_slot":best[2],"enumerated_combinations":considered}
