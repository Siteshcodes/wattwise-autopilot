import pytest

from wattwise.solver_v2.canonical import business_input, digest, schedule_hash
from wattwise.solver_v2.fixtures import demo_request
from wattwise.solver_v2.milp import solve
from wattwise.solver_v2.pipeline import optimize
from wattwise.solver_v2.schema import Options, Request
from wattwise.solver_v2.verify import replay, verify

from .helpers import change


@pytest.fixture(scope="module")
def demo():
    request=demo_request()
    response=optimize(request)
    assert response.status == "BUDGET_MISS", response.message
    assert response.lexicographic_complete
    return request,response


def test_A2_shared_panel_conflict_includes_base_load(demo):
    request,result=demo
    plan=result.schedule
    assert max(plan.total_load_kw) <= 9.6+1e-6
    for t in range(96):
        expected=request.base_load_kw[t]+plan.ev_power_kw[t]+request.washer.power_kw*plan.washer_on[t]+request.hvac.power_kw*plan.hvac_on[t]
        assert plan.total_load_kw[t] == pytest.approx(expected,abs=1e-6)
    # These independent device decisions meet C1-C6/C8, but together overload C7.
    naive=replay(request,[7.2 if 8 <= t < 52 else 0 for t in range(96)],8,[1]*96)
    checks={c.key:c for c in verify(request,naive)}
    assert max(naive.total_load_kw) == pytest.approx(15.2)
    assert not checks["C7.panel_including_base"].satisfied
    assert all(c.satisfied for key,c in checks.items() if key != "C7.panel_including_base")
    assert max(plan.ev_power_kw) < 7.2


def test_A3_washer_exactly_once_uninterrupted_within_window(demo):
    request,result=demo
    plan,w=result.schedule,request.washer
    active=[t for t,on in enumerate(plan.washer_on) if on]
    assert len(active) == w.duration_slots
    assert active == list(range(plan.washer_start_slot,plan.washer_start_slot+w.duration_slots))
    assert w.earliest_start_slot <= active[0]
    assert active[-1] < w.must_finish_by_slot


def test_A4_all_97_thermal_boundaries_and_minimum_durations(demo):
    request,result=demo
    assert len(result.schedule.temperature_c)==97
    assert all(request.hvac.min_temp_c-1e-6 <= t <= request.hvac.max_temp_c+1e-6 for t in result.schedule.temperature_c)
    checks={c.key:c for c in verify(request,result.schedule)}
    assert checks["C5.hvac_min_durations_and_boundaries"].satisfied
    # Also solve a 96-slot profile with a real shutdown and a long OFF run.
    cycling=change(request,outdoor_temp_c=[34.8]*24+[24.1]*73,hvac={"initial_temp_c":24.99})
    cycled=solve(cycling)
    assert cycled.status=="OPTIMAL",cycled.message
    assert sum(cycled.schedule.hvac_shutdown)>=1
    assert all(c.satisfied for c in verify(cycling,cycled.schedule))


def test_A5_impossible_physical_returns_diagnostics_without_plan():
    request=change(demo_request(),base_load_kw=[9.7]*96)
    result=optimize(request,Options(workers=1,max_extensions=1))
    assert result.status=="INFEASIBLE_PHYSICAL"
    assert result.schedule is None and result.min_cost_usd is None
    assert result.diagnostics
    assert not any(d["restores_feasibility"] for d in result.diagnostics)
    for d in result.diagnostics:
        if "replay_input" in d:
            revised=Request.model_validate(d["replay_input"])
            assert revised.hvac==request.hvac
            assert revised.base_load_kw==request.base_load_kw
            assert revised.panel_limit_kw==request.panel_limit_kw


def test_A5_actual_deadline_resolve_restores_feasibility():
    request=change(demo_request(),ev={"deadline_slot":12})
    result=optimize(request,Options(workers=1))
    assert result.status=="INFEASIBLE_PHYSICAL" and result.schedule is None
    restored=next(d for d in result.diagnostics if d["dimension"]=="ev_deadline")
    assert restored["restores_feasibility"] is True
    assert restored["solve_result"]["schedule"] is not None
    assert restored["relaxed_to_slot"]==96


def test_A6_budget_miss_actual_counteroffers_independently_resolved(demo):
    request,result=demo
    assert result.min_cost_usd > request.budget_usd+1e-6
    assert result.gap <= 1e-9
    assert 1 <= len(result.counteroffers) <= 3
    assert {c["dimension"] for c in result.counteroffers}=={"budget","ev_deadline"}
    for offer in result.counteroffers:
        revised=Request.model_validate(offer["replay_input"])
        assert revised.hvac==request.hvac
        assert revised.panel_limit_kw==request.panel_limit_kw
        assert revised.ev.power_levels_kw==request.ev.power_levels_kw
        assert revised.ev.efficiency==request.ev.efficiency
        assert revised.ev.required_battery_energy_kwh==request.ev.required_battery_energy_kwh
        rerun=solve(revised)
        assert rerun.status=="OPTIMAL"
        assert rerun.min_cost_usd == pytest.approx(offer["min_cost_usd"],abs=1e-6)
        assert rerun.schedule.cost_usd == pytest.approx(offer["final_cost_usd"],abs=1e-6)
        assert all(c.satisfied for c in verify(revised,rerun.schedule))
        assert schedule_hash(rerun.schedule)==offer["schedule_ref"]
        assert offer["reaches_budget"]
    assert all(c["constraint"]=="ev_deadline" and c["computed_delta_usd"]>1e-6 for c in result.cost_driving)
    assert result.cost_curves["ev_deadline"][0]["smallest_tested_change_reaching_budget"]==56
    assert not any(c["reaches_budget"] for c in result.cost_curves["washer_deadline"])


def test_A7_changed_constraint_produces_different_valid_plan(demo):
    request,result=demo
    revised=change(request,ev={"deadline_slot":56})
    changed=solve(revised)
    assert changed.status=="OPTIMAL"
    assert schedule_hash(changed.schedule)!=schedule_hash(result.schedule)
    assert changed.min_cost_usd < result.min_cost_usd-1e-6
    assert changed.schedule.ev_completion_slot>request.ev.deadline_slot
    assert all(c.satisfied for c in verify(revised,changed.schedule))


def test_A8_replay_canonical_business_hashes(demo):
    request,result=demo
    repeated=optimize(request)
    assert repeated.input_hash==result.input_hash
    assert repeated.output_hash==result.output_hash
    assert repeated.schedule==result.schedule
    # Worker completion ordering, dict ordering, integer-vs-float literals and
    # transport request IDs are not business changes.
    equivalent=change(request,request_id="another-session",negotiable=list(reversed(request.negotiable)))
    serial=optimize(equivalent,Options(workers=1))
    assert serial.input_hash==result.input_hash
    assert serial.output_hash==result.output_hash
    assert digest({"a":1,"b":-0.0})==digest({"b":0,"a":1.0})
    assert digest(business_input(change(request,budget_usd=49)))!=digest(business_input(request))


def test_firm_goals_never_relaxed_or_offered():
    request=change(demo_request(),ev={"deadline_tier":"firm"},washer={"deadline_tier":"firm"},budget_tier="firm")
    result=optimize(request)
    assert result.status=="BUDGET_MISS"
    assert result.counteroffers==[] and result.cost_curves=={}
    assert result.schedule.ev_completion_slot<=52
    impossible=change(request,ev={"deadline_slot":12})
    assert optimize(impossible).diagnostics==[]


def test_budget_scope_changes_cost_not_panel_or_feasibility(demo):
    request,result=demo
    controllable=change(request,budget_scope="controllable",budget_usd=100)
    other=solve(controllable)
    assert other.status=="OPTIMAL"
    base=sum(c*request.dt*p for c,p in zip(request.tariff_usd_per_kwh,request.base_load_kw))
    assert result.min_cost_usd-other.min_cost_usd==pytest.approx(base,abs=1e-6)
    assert all(c.satisfied for c in verify(controllable,other.schedule))


def test_invalid_replay_is_rejected(demo):
    request,result=demo
    forged=result.schedule.model_copy(deep=True)
    forged.hvac_startup[0]=1  # initial ON: there was no startup at t=0
    assert not all(c.satisfied for c in verify(request,forged))
