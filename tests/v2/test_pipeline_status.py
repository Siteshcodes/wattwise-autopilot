import highspy

from wattwise.solver_v2 import milp
from wattwise.solver_v2.fixtures import demo_request
from wattwise.solver_v2.pipeline import optimize
from wattwise.solver_v2.schema import Options

from .helpers import change, small_request


def test_actual_primary_timeout_preserves_valid_incumbent_not_minimum(monkeypatch):
    original_run=milp._run
    def force_primary_timeout(problem,objective,offset,stage,units,options):
        if stage=="minimum_cost":
            options=Options(time_limit_s=0)
        return original_run(problem,objective,offset,stage,units,options)
    monkeypatch.setattr(milp,"_run",force_primary_timeout)
    result=optimize(small_request(),Options(workers=1),small_instance=True)
    assert result.status=="TIME_LIMIT"
    assert result.min_cost_usd is None
    assert result.schedule is not None  # independently validated Stage 0 incumbent
    assert all(c.satisfied for c in result.constraint_report)
    assert result.counteroffers==[]
    assert not result.lexicographic_complete


def test_actual_secondary_timeout_reports_incomplete_lexicographic_solve(monkeypatch):
    original_run=milp._run
    def force_secondary_timeout(problem,objective,offset,stage,units,options):
        if stage=="fewest_hvac_switches":
            options=Options(time_limit_s=0)
        return original_run(problem,objective,offset,stage,units,options)
    monkeypatch.setattr(milp,"_run",force_secondary_timeout)
    result=optimize(small_request(),Options(workers=1),small_instance=True)
    assert result.status=="TIME_LIMIT"
    assert result.min_cost_usd is not None  # primary genuinely proved before timeout
    assert not result.lexicographic_complete
    assert result.counteroffers==[]


def test_impossible_budget_preserves_physical_plan_and_all_cost_curves():
    request=change(demo_request(),budget_usd=0)
    result=optimize(request,Options(workers=1))
    assert result.status=="BUDGET_MISS"
    assert result.schedule is not None
    assert len(result.cost_curves["ev_deadline"])==4
    assert not any(p["reaches_budget"] for p in result.cost_curves["ev_deadline"])
    assert not any(p["reaches_budget"] for p in result.cost_curves["washer_deadline"])
    assert result.persist["decisions"][0]["action_applied"] is False
    assert result.persist["preference_updates"]==[]


def test_budget_numerical_tolerance_not_display_rounding():
    request=demo_request()
    minimum=milp.solve(request).min_cost_usd
    barely_within=optimize(change(request,budget_usd=minimum-5e-7),Options(workers=1))
    assert barely_within.status=="OPTIMAL_WITHIN_BUDGET"
    below=optimize(change(request,budget_usd=minimum-.001,negotiable=[]),Options(workers=1))
    assert below.status=="BUDGET_MISS"  # both amounts round to the same cent
