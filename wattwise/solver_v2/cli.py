import argparse
import json
from pathlib import Path

from .fixtures import demo_request
from .pipeline import optimize
from .schema import Options, Request


def summary(request,response):
    plan=response.schedule
    return {
        "scenario":"Constructed household on a real published PG&E tariff snapshot; devices and thermal coefficients are examples, uncalibrated.",
        "status":response.status,"min_cost_usd":response.min_cost_usd,
        "schedule_cost_usd":plan.cost_usd if plan else None,"budget_usd":request.budget_usd,
        "lower_bound_usd":response.lower_bound_usd,"gap":response.gap,
        "lexicographic_complete":response.lexicographic_complete,
        "peak_total_load_kw":max(plan.total_load_kw) if plan else None,
        "washer_start_slot":plan.washer_start_slot if plan else None,
        "ev_completion_slot":plan.ev_completion_slot if plan else None,
        "ev_battery_energy_kwh":plan.ev_battery_energy_kwh if plan else None,
        "temperature_range_c":[min(plan.temperature_c),max(plan.temperature_c)] if plan else None,
        "hvac_switches":plan.hvac_switches if plan else None,
        "constraint_checks_passed":all(c.satisfied for c in response.constraint_report) if plan else None,
        "panel_conflict_evidence":{
            "requested_ev_max_kw":max(request.ev.power_levels_kw),
            "max_ev_plus_base_hvac_washer_kw":max(request.base_load_kw)+max(request.ev.power_levels_kw)+request.hvac.power_kw+request.washer.power_kw,
            "panel_limit_kw":request.panel_limit_kw,
            "washer_overlap_ev_levels_kw":sorted(set(plan.ev_power_kw[t] for t,w in enumerate(plan.washer_on) if w)) if plan else [],
        },
        "counteroffers":[{k:c[k] for k in ("dimension","change","final_cost_usd","ev_delay_minutes","washer_delay_minutes","reaches_budget","schedule_ref")} for c in response.counteroffers],
        "cost_curves":{key:[{k:p[k] for k in ("value","status","min_cost_usd","gap","reaches_budget")} for p in points] for key,points in response.cost_curves.items()},
        "cost_driving":response.cost_driving,"input_hash":response.input_hash,"output_hash":response.output_hash,
    }


def main():
    parser=argparse.ArgumentParser(description="WattWise V2 solver only; produces proposals, never device actions")
    parser.add_argument("--request",type=Path,help="A JSON request with exactly 96 slots")
    parser.add_argument("--demo",action="store_true",help="Run the constructed, published-tariff panel conflict")
    parser.add_argument("--output",type=Path,help="Save the full machine-readable result")
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    if bool(args.request)==bool(args.demo):
        parser.error("Specify exactly one of --demo or --request")
    request=Request.model_validate_json(args.request.read_text()) if args.request else demo_request()
    response=optimize(request,Options(workers=args.workers))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(response.model_dump_json(indent=2),encoding="utf-8")
    print(json.dumps(summary(request,response),indent=2))
    return 1 if response.status in ("ERROR","TIME_LIMIT") else 0


if __name__ == "__main__":
    raise SystemExit(main())
