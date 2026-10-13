from datetime import datetime

from wattwise.solver_v2.schema import Request


def small_request(n=6):
    return Request(
        request_id=f"small-{n}",horizon_start=datetime.fromisoformat("2026-10-22T18:00:00-07:00"),
        tariff_dataset_id="synthetic-oracle-only",tariff_usd_per_kwh=[.4,.3,.1,.1,.2,.2,.3,.1][:n],
        base_load_kw=[5.8]*n,outdoor_temp_c=[30]*(n+1),panel_limit_kw=9.6,
        ev={"required_battery_energy_kwh":1.62,"power_levels_kw":[0,1.8,3.6],"efficiency":.9,"available_from_slot":0,"deadline_slot":n},
        washer={"power_kw":1.8,"duration_slots":2,"earliest_start_slot":0,"must_finish_by_slot":n},
        hvac={"power_kw":3,"initial_temp_c":24.8,"min_temp_c":22,"max_temp_c":25,"tau_hours":6,"cooling_per_slot_c":.4},
        budget_usd=50,budget_scope="total_home",negotiable=["budget","ev_deadline","washer_deadline"])


def change(request, **updates):
    body=request.model_dump(mode="json")
    for key,value in updates.items():
        if isinstance(value,dict):
            body[key].update(value)
        else:
            body[key]=value
    return Request.model_validate(body)
