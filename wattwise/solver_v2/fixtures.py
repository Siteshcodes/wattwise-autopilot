import json
from datetime import datetime, timedelta
from pathlib import Path

from .schema import Request


def demo_request() -> Request:
    snapshot = json.loads((Path(__file__).resolve().parents[2]/"docs/tariffs/pge-ev2-winter-2026-06-01.json").read_text())
    start = datetime.fromisoformat("2026-10-22T18:00:00-07:00")
    prices=[]
    for t in range(96):
        hour=(start+timedelta(minutes=15*t)).hour
        period="peak" if 16 <= hour < 21 else "partial_peak" if hour >= 21 or hour == 15 else "off_peak"
        prices.append(snapshot["rates"][period])
    return Request(
        request_id="panel-conflict-demo-001",horizon_start=start,tariff_dataset_id=snapshot["dataset_id"],
        tariff_usd_per_kwh=prices,base_load_kw=[3.0]*96,outdoor_temp_c=[34.8]*97,
        panel_limit_kw=9.6,
        ev={"required_battery_energy_kwh":24,"power_levels_kw":[0,1.8,3.6,5.4,7.2],"efficiency":.9,"available_from_slot":8,"deadline_slot":52,"deadline_tier":"stated"},
        washer={"power_kw":2,"duration_slots":6,"earliest_start_slot":8,"must_finish_by_slot":28},
        hvac={"power_kw":3,"initial_temp_c":24.99,"min_temp_c":22,"max_temp_c":25,"tau_hours":6,"cooling_per_slot_c":.4,"cooling_cop":3,"initial_on":1,"initial_state_elapsed_slots":2},
        budget_usd=49.5,budget_scope="total_home",preference_scope="standing",
        negotiable=["budget","washer_deadline","ev_deadline"])
