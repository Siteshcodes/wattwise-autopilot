# WattWise V2 — Advanced Constraint Solver

Authoritative requirements: [wattwise-solver-spec-v2.md](../wattwise-solver-spec-v2.md).
This phase implements Gate A. The existing V1 MCP server, endpoints, SQLite
device flow, dashboard, and its 13 tests are unchanged.

## Implementation plan and delivered modules

1. `schema.py`: validated 15-minute request/result models, explicit units,
   stated/firm tiers, HVAC initial state and elapsed state duration.
2. `milp.py`: HiGHS feasibility, minimum cost, fewest HVAC switches and earliest
   EV completion solves; all physical/protected constraints and exact transitions.
3. `verify.py` and `oracle.py`: independent physical replay/constraint audit and
   an exhaustive discrete 6–8-slot verifier, independent of the MILP builder.
4. `pipeline.py` and `canonical.py`: actual relaxation solves, diagnostics,
   Pareto filtering, cost-driving evidence, and canonical business-data hashes.
5. `fixtures.py`, `cli.py`, `tests/v2`: a reproducible 96-slot panel conflict,
   full JSON evidence and A1–A8 regressions.

## Run locally

From the repository root with Python 3.12:

```powershell
.\.venv\Scripts\python -m pip install -e ".[test,solver]"
.\.venv\Scripts\python -m pytest tests/v2 -q
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m wattwise.solver_v2.cli --demo
.\.venv\Scripts\python -m wattwise.solver_v2.cli --request docs/v2-demo-request.json --output data/v2-result.json
```

The optional solver extra pins HiGHS/highspy 1.15.1 and NumPy 2.5.4. The V1
dependency lock remains unchanged; `requirements-solver-lock.txt` records the
additional pinned packages. V2 requires no AWS credentials or running servers.
On Linux/macOS use `.venv/bin/python` instead.

The CLI exits nonzero on `TIME_LIMIT` or `ERROR`. Schema validation fails loudly
before solving. The default production API requires exactly 96 tariff/base slots
and 97 outdoor boundary temperatures. `small_instance=True` is an explicit test
mode used for the exhaustive verifier, never a production-grid shortcut.

## Physical model and boundary conventions

- A one-hot binary selects an EV level in every slot. Positive levels outside
  the plug-in/deadline window have upper bound zero. The deadline is exclusive.
- Battery energy is efficiency × slot hours × sum of grid power. The inequality
  is `>= required_battery_energy_kwh`; discrete levels can cause a small excess.
  A valid integer-lattice cut strengthens the relaxation without rounding or
  altering the requested energy.
- Washer start binaries exist only at permitted starts. Exactly one must be
  selected. Their convolution defines one uninterrupted fixed-length run.
- Panel load includes base + EV + washer + HVAC in every slot, independent of
  the selected budget scope.
- Temperature variables include **all 97 boundary states**, with protected
  lower and upper bounds. Initial temperature is a separate equality; an
  incompatible initial temperature is physical infeasibility.
- HVAC startup `z` and shutdown `q` are both binary, with
  `z[t] - q[t] = h[t] - h[t-1]` and `z[t] + q[t] <= 1`. Thus neither can be
  invented as an optional/spurious event. `h[-1]` is the supplied `initial_on`.
- Sliding startup/shutdown sums enforce minimum on/off durations. At t=0,
  `initial_state_elapsed_slots` counts completed slots in the supplied initial
  state immediately before the horizon. Any outstanding minimum duration fixes
  the corresponding prefix of `h` to that state.
- Terminal policy is explicit: **complete_within_horizon**. A new startup or
  shutdown is forbidden when its full minimum duration cannot finish before N.
  This avoids silently truncating a run. An existing pre-horizon state can
  continue unchanged throughout the horizon. No future thermal forecast or
  future actuator execution is claimed.
- Cooling-only inputs require every outdoor temperature, including the supplied
  final forecast boundary, to be strictly above the protected lower bound.
  Heating mode is not implemented.

## Thermal coefficients and units

The continuous model is

```
C * dT/dt = U * (T_out - T) - COP * P_H * h
tau = C / U
a = exp(-dt / tau)
b = (1-a) * COP * P_H / U
T[t+1] = a*T[t] + (1-a)*T_out[t] - b*h[t]
```

For the accepted example `dt=0.25 h`, `tau=6 h`, `COP=3`, `P_H=3 kW`, and
`b=0.4 C/ON-slot`, the implied coefficients are:

- `a = 0.9591894571091382` (dimensionless).
- `U = 0.9182372150443913 kW/C`.
- `C = 5.509423290266348 kWh/C`.

These values use exact constant-input RC discretization, and b includes COP.
They are documented **constructed coefficients, not calibration results**.
Thermal dynamics can also be tested with other validated request coefficients.

## Status, tolerances and proof

Each HiGHS run uses one thread, parallel search off, seed 0, requested relative
and absolute MIP gaps zero, and a **2-second time limit per run**. The whole
pipeline can take longer: the baseline has four sequential runs, and each
candidate has its own runs. Counteroffer candidates execute in separate parallel
processes (up to four) to isolate HiGHS's global thread scheduler. Returned
candidate order follows job order, not completion order.

1. Feasibility includes all physical/protected constraints and current deadlines,
   without a budget constraint. No feasible solution means
   `INFEASIBLE_PHYSICAL`, not an invented price or schedule.
2. Primary cost is solved to optimality before it is labeled `min_cost_usd`.
3. Cost is fixed within `1e-7 USD` for the switch-count solve; the proved minimum
   switch count is then fixed for earliest EV charge completion. The final
   schedule's actual cost is separately retained.
4. Budget comparison uses `1e-6 USD` numerical tolerance. It does not use
   display-rounded cents. All returned schedule values and costs retain precision.
5. A timed-out primary solve exposes a validated incumbent and its bound/gap when
   available, but **no claimed minimum**. A timed-out secondary solve returns
   `TIME_LIMIT` with `lexicographic_complete=false`, even if primary cost was
   proved. Per-stage evidence states the objective units and proof status.
6. Decoding checks raw integer decisions, solver temperature states, and exact
   startup/shutdown values. An independent replay then verifies the published
   schedule. Constraint reports include numerical slacks, units and satisfaction
   using a `1e-6` tolerance. HiGHS feasibility tolerance is `1e-7`.

The raw reported gap can be a tiny floating-point residual such as `2e-15`.
Optimal certificates require native HiGHS `Optimal` status and a gap no larger
than `1e-9`; unresolved time limits never acquire that label.

## Counteroffers and preferences

Only dimensions present in `negotiable` **and** carrying tier `stated` may change.
Firm budget, EV deadline and washer deadline are honored in every solve.
Comfort, panel capacity, load profiles, charging power/efficiency/energy, HVAC
physics, washer cycle length and plug-in availability are never relaxed.

Every offered alternative includes its changed request, full separately solved
result, and schedule reference/hash. Even raising budget is re-solved and
re-verified. The default deadline sweep tests four one-hour extensions, clipped
to the existing horizon. A response includes the whole tested cost curve and
the smallest tested extension that reaches the budget, if any. It does not claim
to have searched arbitrary minute extensions or times beyond the horizon.

Physical infeasibility diagnostics separately re-solve permitted deadline
relaxations to the end of the horizon. Budget is explicitly diagnosed as absent
from the feasibility model. A validated alternate incumbent can demonstrate
restored feasibility even when its minimum cost has not been proved.

Pareto comparison uses final cost, EV delay minutes and washer delay minutes.
Dominated offers are dropped; at most three are presented. Cost-driving claims
are made only from proved lower costs in actual re-solves. A firm or exhausted
goal yields the proved minimum with the miss stated and no automatic action.

The default preference scope is `standing`. This phase consumes tiers/scope in
the request and emits proposal-only persistence intentions; it does not persist
new preference state across sessions. The `persist` output explicitly records
`approval_required=true` and `action_applied=false`.

## Canonical replay

Business input hashes include the model/backend version, validated request
values and fixed solve settings. JSON keys are sorted; numeric values are
normalized through Decimal strings, so `1`/`1.0` and `-0`/`0` are equivalent.
The negotiable set is sorted. Transport request IDs and worker count are excluded.

The output hash covers business decisions, reconstructed schedules, costs,
constraint slacks, offers, diagnostics and their replay inputs. Transport IDs,
raw solver bounds/gaps and per-stage diagnostics are excluded recursively;
they remain in the full evidence document. Nothing is rounded for hashing.
The hash is a deterministic business replay identifier, not a byte checksum of
the complete JSON response. Schedule hashes cover the full replayed schedule.

Certified replays are tested with the pinned backend, one thread and seed 0.
Wall-clock cutoff outcomes on difficult instances can vary with hardware/load;
their honest `TIME_LIMIT` evidence is retained rather than promising a completed
optimum or identical interrupted-search trajectory.

## Actual demo

Inputs: [v2-demo-request.json](v2-demo-request.json).
Full computed output: [v2-demo-result.json](v2-demo-result.json).
Tariff provenance: [frozen snapshot](tariffs/pge-ev2-winter-2026-06-01.json).

The rates are transcribed from PG&E's official EV2 sheet 61374-E, effective
1 June 2026: winter peak `0.41099`, partial peak `0.39428`, off-peak `0.22558`
USD/kWh. Timing follows sheet 4: peak 16:00–21:00, partial peak 15:00–16:00
and 21:00–24:00, off-peak otherwise.
[Official tariff](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_EV2%20(Sch).pdf).
This is a historical published energy-price snapshot, excluding fixed charges,
taxes and customer-specific adjustments, not a live tariff or complete bill.

The household is **constructed on real tariff data**. Horizon: 22 October 2026
18:00 through 23 October 18:00, fixed Pacific offset `-07:00`. Base load is
3 kW, outdoor temperature 34.8 C, initial temperature 24.99 C. This high cooling
stress fixture requires HVAC ON throughout the horizon. A separate 96-slot
test changes the outdoor profile and exercises an actual shutdown; small-instance
oracle tests exercise HVAC on/off decisions and transitions.

The EV needs 24 battery kWh at 90% efficiency, is plugged in at 20:00 and must
finish by 07:00. Washer draws 2 kW for six slots, can start after 20:00, and must
finish by 01:00. Independent valid device choices together would draw **15.2 kW**;
the panel permits only **9.6 kW**. The test verifies that this naive plan violates
only the panel constraint, demonstrating an actual multi-device conflict.

Observed solver output:

| Quantity | Computed value |
|---|---|
| Status | BUDGET_MISS |
| Proven minimum / final schedule cost | $49.67178 |
| Budget, total-home scope | $49.50 |
| Lower bound | $49.6717799999999 |
| Raw primary gap | 2.002665960559779e-15 |
| Peak load, including base | 9.6 kW |
| EV grid / battery energy | 27 / 24.3 kWh |
| EV completion | slot 52, 07:00 |
| Washer | slots 17–22, 22:15–23:45 |
| Temperature over all 97 boundaries | 24.99–24.998453432559693 C |
| HVAC | ON throughout; initial state ON; zero switches |

Actually re-solved offers, all requiring future human approval:

| Change | Final modeled cost | Meets revised budget? |
|---|---|---|
| Raise budget to $49.67178; keep deadlines | $49.67178 | Yes |
| EV deadline 08:00 instead of 07:00 | $49.19942 | Yes |
| EV deadline 09:00 instead of 07:00 | $49.03072 | Yes |

The second deadline offer's earliest actual completion is 08:30 (slot 58),
inside its 09:00 deadline. The 08:00 extension saves $0.47236 relative to the
original minimum. Washer deadline extensions do not reduce the proved cost;
the response retains those negative findings and makes no cost-driving claim.
No device action or preference change was executed.

## Gate A and remaining work

Verification on 13 October 2026: `python -m pytest -q` reported **41 passed in
42.02 s**, comprising **13 preserved V1 tests + 28 V2 tests**. `pip check`
reported no broken requirements. A1–A8 are **PASS**; no Gate A item is FAIL or
NOT IMPLEMENTED. Gate B items remain NOT IMPLEMENTED in this phase.

| Gate | Regression evidence |
|---|---|
| A1 | 6-, 7-, and 8-slot MILP vs independent exhaustive discrete enumeration; integer-cent and full-precision cost checks; secondary objectives checked |
| A2 | 96-slot panel audit includes base; independently valid naive plan demonstrably overloads panel |
| A3 | Exactly one six-slot contiguous washer cycle inside the permitted window |
| A4 | All 97 temperature bounds; varying-temperature 96-slot shutdown; initial residual and terminal-duration regressions |
| A5 | Impossible base-load and impossible deadline cases; real permitted diagnostic re-solves; no original schedule |
| A6 | Proved budget miss; every offered request independently re-solved, audited and hash-checked; zero-budget exhaustion tested |
| A7 | One-hour EV deadline change creates a different valid and cheaper plan |
| A8 | Repeated hashes match across parallel/serial candidates and canonical metadata variants |

Additional tests cover actual zero-time-limit solver runs at feasibility,
primary and secondary stages, strict input validation, protected comfort
conflicting with an initial HVAC obligation, malformed replay evidence, firm
constraints, budget scope and numerical comparisons below a display cent.

**Not implemented in this phase:** Gate B standing-preference persistence,
rejection/authorization workflow, LLM explanation numeric audits and V2 approval
through MCP. V1 approval/MCP/persistence still work. AWS, voice and dashboard
enhancements are out of scope. Heating, building calibration, beyond-horizon
continuation, multi-EV/multi-washer instances and packaged solver deployment are
also outside this model. The exact thermal MILP can reach its time limit on
harder 96-slot profiles; that is reported honestly and no optimality is inferred.
