import pytest

from wattwise.solver_v2.milp import solve
from wattwise.solver_v2.oracle import brute_force
from wattwise.solver_v2.schema import Options, Request
from wattwise.solver_v2.verify import verify

from .helpers import change, small_request


@pytest.mark.parametrize("n",[6,7,8])
def test_A1_milp_equals_discrete_brute_force(n):
    request=small_request(n)
    result=solve(request,small_instance=True)
    oracle=brute_force(request)
    assert result.status == oracle["status"] == "OPTIMAL", result.message
    assert round(result.min_cost_usd*100) == round(oracle["cost_usd"]*100)
    assert result.min_cost_usd == pytest.approx(oracle["cost_usd"],abs=1e-6)
    assert result.schedule.hvac_switches == oracle["hvac_switches"]
    assert result.schedule.ev_completion_slot == oracle["ev_completion_slot"]
    assert result.gap == 0
    assert all(c.satisfied for c in verify(request,result.schedule))
    assert all(e.proven_optimal for e in result.evidence)


@pytest.mark.parametrize("on,elapsed",[(0,0),(0,1),(1,0),(1,1)])
def test_initial_hvac_residual_minimum_and_oracle(on,elapsed):
    request=change(small_request(),outdoor_temp_c=[26]*7,hvac={"initial_temp_c":24,"initial_on":on,"initial_state_elapsed_slots":elapsed})
    result=solve(request,small_instance=True)
    oracle=brute_force(request)
    assert result.status == oracle["status"]
    if result.schedule:
        assert result.schedule.hvac_on[:2-elapsed] == [on]*(2-elapsed)
        assert result.min_cost_usd == pytest.approx(oracle["cost_usd"],abs=1e-6)


def test_final_temperature_boundary_is_protected():
    request=change(small_request(),hvac={"initial_temp_c":24,"initial_state_elapsed_slots":99},outdoor_temp_c=[26]*5+[40,26])
    # Without cooling, every slot start is comfortable, but the final boundary is not.
    from wattwise.solver_v2.verify import replay
    forged=replay(request,[0]*6,0,[0]*6)
    assert max(forged.temperature_c[:-1]) <= 25
    assert forged.temperature_c[-1] > 25
    report={c.key:c for c in verify(request,forged)}
    assert not report["C8.comfort_upper"].satisfied
    result=solve(request,small_instance=True)
    assert result.status == "OPTIMAL"
    assert sum(result.schedule.hvac_on) >= 2
    assert result.schedule.temperature_c[-1] <= 25+1e-6
    assert all(c.satisfied for c in verify(request,result.schedule))


def test_initial_on_residual_conflicting_with_comfort_is_infeasible():
    request=change(small_request(),outdoor_temp_c=[22.1]*7,hvac={"initial_temp_c":22,"initial_on":1,"initial_state_elapsed_slots":1})
    result=solve(request,small_instance=True)
    assert result.status == "INFEASIBLE_PHYSICAL"
    assert result.schedule is None
    assert brute_force(request)["status"] == "INFEASIBLE_PHYSICAL"


def test_no_truncated_terminal_hvac_transitions():
    request=change(small_request(),outdoor_temp_c=[26]*7,hvac={"initial_temp_c":24,"initial_state_elapsed_slots":99})
    from wattwise.solver_v2.verify import replay
    for states in [[0,0,0,0,0,1],[0,0,1,1,1,0]]:
        report={c.key:c for c in verify(request,replay(request,[0]*6,0,states))}
        assert not report["C5.hvac_min_durations_and_boundaries"].satisfied


def test_validation_cooling_only_and_shapes_and_grid():
    request=small_request()
    with pytest.raises(ValueError,match="Cooling-only"):
        change(request,outdoor_temp_c=[22]*7)
    with pytest.raises(ValueError,match="N tariffs"):
        change(request,base_load_kw=[0])
    with pytest.raises(ValueError,match="96 slots"):
        solve(request)
    body=request.model_dump(mode="json")
    body["tariff_usd_per_kwh"][0]=float("nan")
    with pytest.raises(ValueError):Request.model_validate(body)


def test_timeout_is_not_proven_optimal():
    result=solve(small_request(),Options(time_limit_s=0),small_instance=True)
    assert result.status == "TIME_LIMIT"
    assert result.min_cost_usd is None
    assert not result.lexicographic_complete
    assert not all(e.proven_optimal for e in result.evidence)


def test_decimal_ev_levels_do_not_create_ill_scaled_lattice_cut():
    request=change(small_request(),ev={"power_levels_kw":[0,1.8,3.6000000000000005]})
    result=solve(request,small_instance=True)
    oracle=brute_force(request)
    assert result.status==oracle["status"]=="OPTIMAL"
    assert result.min_cost_usd==pytest.approx(oracle["cost_usd"],abs=1e-6)
