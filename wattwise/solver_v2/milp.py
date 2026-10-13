"""HiGHS MILP with exact binary transitions and three lexicographic objectives."""
from fractions import Fraction
from functools import reduce
from math import ceil, fsum, gcd, isfinite, lcm

import highspy
import numpy as np

from .schema import Evidence, Options, Request, SolveResult
from .verify import replay, verify

INF = highspy.kHighsInf


class Matrix:
    def __init__(self):
        self.lower, self.upper, self.integer = [], [], []
        self.rows, self.row_lower, self.row_upper = [], [], []

    def variable(self, low=0, high=1, integer=True):
        index = len(self.lower)
        self.lower.append(low)
        self.upper.append(high)
        self.integer.append(highspy.HighsVarType.kInteger if integer else highspy.HighsVarType.kContinuous)
        return index

    def row(self, terms, low=-INF, high=INF):
        self.rows.append({i: v for i,v in terms.items() if v})
        self.row_lower.append(low)
        self.row_upper.append(high)

    def lp(self, objective, offset=0):
        lp = highspy.HighsLp()
        lp.num_col_, lp.num_row_ = len(self.lower), len(self.rows)
        lp.col_cost_, lp.offset_ = objective, offset
        lp.col_lower_, lp.col_upper_ = self.lower, self.upper
        lp.integrality_ = self.integer
        lp.row_lower_, lp.row_upper_ = self.row_lower, self.row_upper
        starts, indices, values = [0], [], []
        for row in self.rows:
            for i,v in sorted(row.items()):
                indices.append(i)
                values.append(v)
            starts.append(len(indices))
        lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
        lp.a_matrix_.start_ = np.asarray(starts, dtype=np.int32)
        lp.a_matrix_.index_ = np.asarray(indices, dtype=np.int32)
        lp.a_matrix_.value_ = np.asarray(values, dtype=float)
        return lp


class Problem:
    def __init__(self, request: Request):
        r, n, h = request, request.n, request.hvac
        self.request, self.matrix = r, Matrix()
        m = self.matrix
        self.ev = []
        for t in range(n):
            available = r.ev.available_from_slot <= t < r.ev.deadline_slot
            self.ev.append([m.variable(high=1 if available or k == 0 else 0) for k in r.ev.power_levels_kw])
        self.starts = {t: m.variable() for t in range(r.washer.earliest_start_slot, r.washer.must_finish_by_slot-r.washer.duration_slots+1)}
        self.hvac = [m.variable() for _ in range(n)]
        self.up = [m.variable(high=int(t+h.min_on_slots <= n)) for t in range(n)]
        self.down = [m.variable(high=int(t+h.min_off_slots <= n)) for t in range(n)]
        self.temp = [m.variable(low=h.min_temp_c, high=h.max_temp_c, integer=False) for _ in range(n+1)]
        self.completion = m.variable(high=n, integer=True)
        self.power = [dict(zip(self.ev[t],r.ev.power_levels_kw)) for t in range(n)]
        self.washer = [{s: 1 for u,s in self.starts.items() if u <= t < u+r.washer.duration_slots} for t in range(n)]
        for t in range(n):
            m.row({i:1 for i in self.ev[t]},1,1)
            positive = {i:-(t+1) for k,i in zip(r.ev.power_levels_kw,self.ev[t]) if k>0}
            m.row({self.completion:1, **positive},low=0)
        m.row({i:r.ev.efficiency*r.dt*k for powers in self.power for i,k in powers.items()},low=r.ev.required_battery_energy_kwh)
        # Valid lattice cut: integer selections cannot supply a fractional number
        # of the greatest-common-divisor EV energy quantum. Strengthens the LP
        # without rounding the requested energy or relaxing any constraint.
        fractions=[Fraction(str(k)) for k in r.ev.power_levels_kw]
        denominator=lcm(*(f.denominator for f in fractions))
        numerator=reduce(gcd,(int(f*denominator) for f in fractions))
        quantum=Fraction(numerator,denominator)
        required=Fraction(str(r.ev.required_battery_energy_kwh))/(Fraction(str(r.ev.efficiency))*Fraction(str(r.dt))*quantum)
        ticks=ceil(required)
        units={i:int(Fraction(str(k))/quantum) for powers in self.power for i,k in powers.items()}
        # Arbitrary user-supplied decimal levels can have a microscopic GCD.
        # In that case omit this optional cut instead of creating badly scaled
        # coefficients or rounding away a requested physical power level.
        if max(units.values()) <= 10000 and ticks <= 1_000_000:
            m.row(units,low=ticks)
        m.row({s:1 for s in self.starts.values()},1,1)
        for t in range(n):
            # z - q = h[t] - h[t-1], z + q <= 1: exact startup AND shutdown.
            terms = {self.up[t]:1, self.down[t]:-1, self.hvac[t]:-1}
            if t:
                terms[self.hvac[t-1]] = 1
            boundary = -h.initial_on if t == 0 else 0
            m.row(terms,boundary,boundary)
            m.row({self.up[t]:1,self.down[t]:1},high=1)
            # Sliding event sums impose uninterrupted runs and give a stronger LP relaxation.
            m.row({**{self.up[u]:1 for u in range(max(0,t-h.min_on_slots+1),t+1)},self.hvac[t]:-1},high=0)
            m.row({**{self.down[u]:1 for u in range(max(0,t-h.min_off_slots+1),t+1)},self.hvac[t]:1},high=1)
            m.row({self.temp[t+1]:1,self.temp[t]:-r.a,self.hvac[t]:h.cooling_per_slot_c},(1-r.a)*r.outdoor_temp_c[t],(1-r.a)*r.outdoor_temp_c[t])
            panel = {**self.power[t],self.hvac[t]:h.power_kw,**{s:r.washer.power_kw for s in self.washer[t]}}
            m.row(panel,high=r.panel_limit_kw-r.base_load_kw[t])
        m.row({self.temp[0]:1},h.initial_temp_c,h.initial_temp_c)
        minimum = h.min_on_slots if h.initial_on else h.min_off_slots
        for t in range(min(n,max(0,minimum-h.initial_state_elapsed_slots))):
            m.row({self.hvac[t]:1},h.initial_on,h.initial_on)
        self.cost = np.zeros(len(m.lower))
        for t,c in enumerate(r.tariff_usd_per_kwh):
            for i,k in self.power[t].items():
                self.cost[i] += c*r.dt*k
            for s in self.washer[t]:
                self.cost[s] += c*r.dt*r.washer.power_kw
            self.cost[self.hvac[t]] += c*r.dt*h.power_kw
        self.base_cost = fsum(c*r.dt*b for c,b in zip(r.tariff_usd_per_kwh,r.base_load_kw)) if r.budget_scope == "total_home" else 0
        self.switches = np.zeros(len(m.lower))
        self.switches[self.up+self.down] = 1
        self.earliest = np.zeros(len(m.lower))
        self.earliest[self.completion] = 1

    def decode(self, x, tolerance):
        r = self.request
        for i,kind in enumerate(self.matrix.integer):
            if kind == highspy.HighsVarType.kInteger and abs(x[i]-round(x[i])) > tolerance:
                raise ValueError("Solver incumbent contains a nonintegral decision")
        ev = [fsum(k*round(x[i]) for i,k in powers.items()) for powers in self.power]
        starts = [t for t,i in self.starts.items() if round(x[i]) == 1]
        if len(starts) != 1 or any(sum(round(x[i]) for i in levels) != 1 for levels in self.ev):
            raise ValueError("Invalid discrete incumbent")
        plan = replay(r,ev,starts[0],[round(x[i]) for i in self.hvac])
        if any(abs(x[i]-temp) > tolerance for i,temp in zip(self.temp,plan.temperature_c)):
            raise ValueError("Solver temperature differs from physical replay")
        if any(round(x[i]) != v for i,v in zip(self.up,plan.hvac_startup)) or any(round(x[i]) != v for i,v in zip(self.down,plan.hvac_shutdown)):
            raise ValueError("Solver transition variables differ from replay")
        report = verify(r,plan,tolerance)
        if not all(c.satisfied for c in report):
            raise ValueError("Independent validation rejected incumbent")
        return plan, report


def _finite(value):
    return float(value) if isfinite(value) else None


def _run(problem, objective, offset, stage, units, options):
    solver = highspy.Highs()
    settings = {"output_flag":False,"threads":1,"parallel":"off","random_seed":options.seed,"time_limit":options.time_limit_s,"mip_rel_gap":0.0,"mip_abs_gap":0.0,"mip_feasibility_tolerance":1e-7,"primal_feasibility_tolerance":1e-7}
    for key,value in settings.items():
        if solver.setOptionValue(key,value) != highspy.HighsStatus.kOk:
            raise RuntimeError(f"HiGHS rejected fixed option {key}")
    if solver.passModel(problem.matrix.lp(objective,offset)) != highspy.HighsStatus.kOk:
        raise RuntimeError("HiGHS rejected the MILP")
    solver.run()
    status, info, solution = solver.getModelStatus(), solver.getInfo(), solver.getSolution()
    valid = solution.value_valid and info.primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible
    proven = status == highspy.HighsModelStatus.kOptimal and info.mip_gap <= 1e-9
    evidence = Evidence(stage=stage,solver_status=solver.modelStatusToString(status),proven_optimal=proven,
        incumbent_objective=_finite(info.objective_function_value) if valid else None,
        lower_bound=_finite(info.mip_dual_bound),gap=_finite(info.mip_gap),objective_units=units,time_limit_s=options.time_limit_s)
    return status, solution.col_value if valid else None, evidence


def solve(request: Request, options: Options | None = None, *, small_instance=False) -> SolveResult:
    options = options or Options()
    if request.n != 96 and not small_instance:
        raise ValueError("Production requests require 96 slots; small_instance=True is reserved for verifier tests")
    p = Problem(request)
    evidence=[]
    plan, report, primary_cost, lower_bound, gap = None, [], None, None, None
    stages = [("feasibility",np.zeros(len(p.cost)),0,"feasibility"), ("minimum_cost",p.cost,p.base_cost,"USD"), ("fewest_hvac_switches",p.switches,0,"switches"), ("earliest_ev_completion",p.earliest,0,"slots")]
    try:
        for stage,objective,offset,units in stages:
            status,x,record = _run(p,objective,offset,stage,units,options)
            evidence.append(record)
            if x is not None:
                plan, report = p.decode(x,options.feasibility_tolerance)
            if status == highspy.HighsModelStatus.kInfeasible:
                if stage == "feasibility":
                    return SolveResult(status="INFEASIBLE_PHYSICAL",evidence=evidence,message="No plan satisfies the physical, protected, and current deadline constraints; budget was not constrained.")
                return SolveResult(status="ERROR",evidence=evidence,message="A lexicographic restriction unexpectedly became infeasible.")
            if stage == "minimum_cost":
                lower_bound, gap = record.lower_bound, record.gap
                if record.proven_optimal:
                    primary_cost = plan.cost_usd
            if not record.proven_optimal:
                return SolveResult(status="TIME_LIMIT" if status in (highspy.HighsModelStatus.kTimeLimit,highspy.HighsModelStatus.kIterationLimit,highspy.HighsModelStatus.kSolutionLimit) else "ERROR",
                    min_cost_usd=primary_cost,lower_bound_usd=lower_bound,gap=gap,schedule=plan,constraint_report=report,evidence=evidence,
                    message=f"{stage} did not finish with proven optimality; any schedule is a validated incumbent, not a completed lexicographic optimum.")
            if stage == "minimum_cost":
                p.matrix.row({i:float(v) for i,v in enumerate(p.cost) if v},high=primary_cost+options.cost_tolerance_usd-p.base_cost)
            elif stage == "fewest_hvac_switches":
                p.matrix.row({i:1 for i in p.up+p.down},high=round(record.incumbent_objective))
        return SolveResult(status="OPTIMAL",min_cost_usd=primary_cost,lower_bound_usd=lower_bound,gap=gap,
            schedule=plan,constraint_report=report,evidence=evidence,lexicographic_complete=True,message="Primary cost, HVAC switch count and EV completion objectives solved to optimality within declared tolerances.")
    except (RuntimeError,ValueError) as exc:
        return SolveResult(status="ERROR",evidence=evidence,message=str(exc))
