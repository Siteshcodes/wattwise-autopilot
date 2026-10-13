from concurrent.futures import ProcessPoolExecutor

from .canonical import business_input, digest, schedule_hash
from .milp import solve
from .schema import Options, Request, Response, Tier
from .verify import verify


def _updated(request,dimension,value):
    body=request.model_dump(mode="json")
    if dimension == "ev_deadline":
        body["ev"]["deadline_slot"]=value
    elif dimension == "washer_deadline":
        body["washer"]["must_finish_by_slot"]=value
    elif dimension == "budget":
        body["budget_usd"]=value
    else:
        raise ValueError("Only budget or stated deadlines may change")
    return Request.model_validate(body)


def allowed(request,dimension):
    tier={"ev_deadline":request.ev.deadline_tier,"washer_deadline":request.washer.deadline_tier,"budget":request.budget_tier}[dimension]
    return dimension in request.negotiable and tier == Tier.STATED


def _worker(job):
    dimension,value,body,options,small = job
    request=Request.model_validate(body)
    result=solve(request,Options.model_validate(options),small_instance=small)
    return dimension,value,request,result


def _jobs(request,options,small,feasibility=False,min_cost=None):
    jobs=[]
    for dimension in sorted(request.negotiable):
        if not allowed(request,dimension):continue
        if dimension == "budget":
            # Budget is not a MILP constraint. Stage 0 records this explicitly.
            if feasibility:continue
            values=[min_cost]
        else:
            original=request.ev.deadline_slot if dimension == "ev_deadline" else request.washer.must_finish_by_slot
            values=[request.n] if feasibility and original < request.n else [min(request.n,original+4*j) for j in range(1,options.max_extensions+1) if original < request.n]
            values=sorted(set(values))
        for value in values:
            revised=_updated(request,dimension,value)
            jobs.append((dimension,value,revised.model_dump(mode="json"),options.model_dump(mode="json"),small))
    return jobs


def _parallel(jobs,workers):
    if not jobs:return []
    # Separate processes isolate HiGHS's global scheduler. Each solver uses ONE thread.
    if workers == 1:
        return [_worker(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=min(workers,len(jobs))) as pool:
        return list(pool.map(_worker,jobs))  # deterministic input order, not completion order


def _pareto(candidates,tolerance):
    keys=("final_cost_usd","ev_delay_minutes","washer_delay_minutes")
    def dominates(a,b):
        return all(a[k] <= b[k]+(tolerance if k=="final_cost_usd" else 0) for k in keys) and any(a[k] < b[k]-(tolerance if k=="final_cost_usd" else 0) for k in keys)
    frontier=[b for b in candidates if not any(a is not b and dominates(a,b) for a in candidates)]
    frontier.sort(key=lambda c:(not c["reaches_budget"],c["ev_delay_minutes"]+c["washer_delay_minutes"],c["final_cost_usd"],c["dimension"]))
    return frontier[:3]


def _finish(request,response,options):
    h=request.hvac
    # Exact discretization of C*dT/dt = U*(Tout-T) - COP*P*h.
    conductance=(1-request.a)*h.cooling_cop*h.power_kw/h.cooling_per_slot_c
    response.thermal_coefficients={"a":request.a,"a_units":"dimensionless","b":h.cooling_per_slot_c,"b_units":"C per ON slot","cop":h.cooling_cop,"effective_heat_capacity_kwh_per_c":conductance*h.tau_hours,"conductance_kw_per_c":conductance,"source":h.coefficient_source,"calibrated":False}
    response.input_hash=digest({"model":"wattwise-milp-v2.0","highs":"1.15.1","instance":business_input(request),"settings":{k:v for k,v in options.model_dump().items() if k!='workers'}})
    # Raw numerical bound/gap and per-stage solver diagnostics are preserved in the
    # response but excluded from business hashes. Discrete decisions are replayed
    # to reconstruct temperatures, energies, loads and costs without rounding.
    def business_output(value):
        if isinstance(value,dict):
            excluded={"output_hash","evidence","lower_bound_usd","gap","request_id","input_request_id"}
            return {k:business_output(sorted(v) if k=="negotiable" else v) for k,v in value.items() if k not in excluded}
        if isinstance(value,list):
            return [business_output(v) for v in value]
        return value
    body=business_output(response.model_dump(mode="json"))
    response.output_hash=digest(body)
    return response


def optimize(request: Request,options: Options | None = None,*,small_instance=False) -> Response:
    options=options or Options()
    result=solve(request,options,small_instance=small_instance)
    body=result.model_dump(exclude={"status"})
    if result.status != "OPTIMAL":
        response=Response(status=result.status,**body)
        if result.status == "INFEASIBLE_PHYSICAL":
            if allowed(request,"budget"):
                response.diagnostics.append({"dimension":"budget","restores_feasibility":False,"message":"Budget is absent from the feasibility model; raising it cannot restore physical feasibility."})
            for dimension,value,revised,alternative in _parallel(_jobs(request,options,small_instance,True),options.workers):
                response.diagnostics.append({"dimension":dimension,"relaxed_to_slot":value,"status":alternative.status,"restores_feasibility":alternative.schedule is not None,"min_cost_usd":alternative.min_cost_usd,"schedule_ref":schedule_hash(alternative.schedule) if alternative.schedule else None,"replay_input":revised.model_dump(mode="json"),"solve_result":alternative.model_dump(mode="json")})
        return _finish(request,response,options)
    within=result.min_cost_usd <= request.budget_usd+options.feasibility_tolerance
    response=Response(status="OPTIMAL_WITHIN_BUDGET" if within else "BUDGET_MISS",**body)
    response.persist["decisions"]=[{"kind":"proposal_only","input_request_id":request.request_id,"approval_required":True,"action_applied":False}]
    if within:
        return _finish(request,response,options)
    candidates=[]
    alternatives=_parallel(_jobs(request,options,small_instance,min_cost=result.min_cost_usd),options.workers)
    for dimension,value,revised,alternative in alternatives:
        curve={"value":value,"status":alternative.status,"min_cost_usd":alternative.min_cost_usd,"incumbent_cost_usd":alternative.schedule.cost_usd if alternative.schedule else None,"lower_bound_usd":alternative.lower_bound_usd,"gap":alternative.gap,"reaches_budget":alternative.status == "OPTIMAL" and alternative.schedule.cost_usd <= revised.budget_usd+options.feasibility_tolerance,"solve_result":alternative.model_dump(mode="json")}
        response.cost_curves.setdefault(dimension,[]).append(curve)
        if alternative.status != "OPTIMAL":continue
        if not all(c.satisfied for c in verify(revised,alternative.schedule,options.feasibility_tolerance)):
            raise RuntimeError("A counteroffer failed independent replay verification")
        if alternative.min_cost_usd < result.min_cost_usd-options.feasibility_tolerance:
            response.cost_driving.append({"constraint":dimension,"relaxed_value":value,"original_min_cost_usd":result.min_cost_usd,"relaxed_min_cost_usd":alternative.min_cost_usd,"computed_delta_usd":result.min_cost_usd-alternative.min_cost_usd})
        candidates.append({"dimension":dimension,"change":{"from":request.budget_usd if dimension=="budget" else request.ev.deadline_slot if dimension=="ev_deadline" else request.washer.must_finish_by_slot,"to":value},"final_cost_usd":alternative.schedule.cost_usd,"min_cost_usd":alternative.min_cost_usd,"ev_delay_minutes":(revised.ev.deadline_slot-request.ev.deadline_slot)*15,"washer_delay_minutes":(revised.washer.must_finish_by_slot-request.washer.must_finish_by_slot)*15,"reaches_budget":curve["reaches_budget"],"requires_confirmation":True,"schedule_ref":schedule_hash(alternative.schedule),"replay_input":revised.model_dump(mode="json"),"solve_result":alternative.model_dump(mode="json")})
    response.counteroffers=_pareto(candidates,options.feasibility_tolerance)
    for dimension,curve in response.cost_curves.items():
        reached=next((c["value"] for c in curve if c["reaches_budget"]),None)
        for point in curve:
            point["smallest_tested_change_reaching_budget"]=reached
    response.message="Budget is below the proven minimum. Offers were actually re-solved; none is applied. Full tested curves and unresolved solves are retained."
    return _finish(request,response,options)
