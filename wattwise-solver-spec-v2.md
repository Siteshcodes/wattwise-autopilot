# WattWise Autopilot: Solver Specification v2

Scope: constraint model, variables, solve pipeline, I/O contract, test gates.
The solver produces all evidence. The LLM only parses speech into the request object and phrases solver output.

## What changed from v1

1. EV deadline is a **tier state** (`stated` -> `firm`), not a constant.
2. Budget is **not** a hard constraint in the MILP. Physical infeasibility and "too expensive" are separate outcomes.
3. Horizon starts at **18:00 the day before** (not midnight) and includes an EV plug-in slot.
4. EV power uses **discrete levels** in both the MILP and the brute-force verifier.
5. Budget scope is explicit and **base load is in the panel constraint**.
6. Washer start variables are mandatory. HVAC has min on/off time. Thermal coefficients are derived and documented.
7. Test gate is split into Gate A (solver, Oct 13) and Gate B (negotiation, Oct 16).

---

## 1. Time grid

- 96 slots, slot length `dt = 0.25 h`, slot `t` covers `[18:00 + 15 min * t, +15 min)`, `t = 0..95`.
- Day D-1 18:00 is `t = 0`. Day D 18:00 is the end of the horizon (`t = 96`).
- A deadline slot `D_x` is **exclusive**: activity is allowed only in slots `t < D_x`.
  - EV ready by 07:00 on day D = 13 h after start -> `D_EV = 52`.
  - Washer finished by 17:00 on day D = 23 h after start -> `D_W = 92`.
- Temperature is a state at slot boundaries: `T_0 .. T_96` (97 values).

## 2. Parameters

| Symbol | Meaning | Source |
| --- | --- | --- |
| `c_t` | tariff, USD/kWh, t=0..95 | published tariff snapshot (versioned, replayable) |
| `base_t` | uncontrollable base load, kW, t=0..95 | fixed profile in the instance |
| `P_panel` | panel limit, 9.6 kW | request |
| `L` | EV power levels, kW, e.g. {0, 1.8, 3.6, 5.4, 7.2} | request |
| `eta` | EV charging efficiency | request |
| `E_batt` | energy that must reach the battery, kWh | request |
| `avail_EV` | first slot the EV is plugged in | request |
| `D_EV` | EV deadline slot (exclusive) | request, tier-governed |
| `P_W`, `d` | washer power (kW), cycle length (slots) | request |
| `W_min`, `D_W` | washer earliest start slot, finish-by slot (exclusive) | request |
| `P_H` | HVAC electrical power, kW | request |
| `T_init`, `T_min`, `T_max` | initial temp and protected comfort band, C | request |
| `T_out_t` | outdoor temp, C, t=0..96 | forecast snapshot |
| `tau_H`, `b` | thermal time constant (h), cooling effect per ON slot (C) | documented, validated |
| `m_on`, `m_off` | HVAC min on / min off, slots | request (default 2) |
| `a` | `exp(-dt / tau_H)` | derived |
| `budget`, `budget_scope` | USD, `"total_home"` or `"controllable"` | request |

`E_batt` is energy **into the battery**. Grid energy for the EV is `E_batt / eta`.

## 3. Decision variables

| Variable | Type | Domain | Meaning |
| --- | --- | --- | --- |
| `e[t,k]` | binary | t=0..95, k in L | EV runs at level k in slot t |
| `p[t]` | derived | kW | `sum_k k * e[t,k]` |
| `s[t]` | binary | t=W_min..D_W-d | washer cycle **starts** in slot t |
| `w[t]` | derived | {0,1} | `sum_{u=max(0,t-d+1)}^{t} s[u]` |
| `h[t]` | binary | t=0..95 | HVAC ON in slot t |
| `z[t]` | binary | t=0..95 | HVAC turns on at slot t (for min on/off) |
| `T[t]` | continuous | t=0..96 | indoor temperature, C |

## 4. Constraints

**Physical (Tier 0, never relaxed)**

- C1. One level per slot: `sum_k e[t,k] = 1` for every t.
- C2. EV availability and deadline: `e[t,0] = 1` for `t < avail_EV` and for `t >= D_EV`.
- C3. EV energy: `eta * dt * sum_t p[t] >= E_batt`.
- C4. Washer runs once, uninterrupted: `sum_t s[t] = 1`, and `s[t] = 0` outside `[W_min, D_W - d]`. `w[t]` as defined in section 3.
- C5. HVAC switching: `z[t] >= h[t] - h[t-1]` (with `h[-1] = 0`).
  Min on-time: for each t and each `u` in `t .. t+m_on-1`, `h[u] >= z[t]`.
  Min off-time: for each t and each `u` in `t .. t+m_off-1`, `h[u] <= 1 - (h[t-1] - h[t])`.
- C6. Thermal dynamics: `T[0] = T_init`; `T[t+1] = a*T[t] + (1-a)*T_out[t] - b*h[t]` for t=0..95.
- C7. Panel: `base[t] + p[t] + P_W*w[t] + P_H*h[t] <= P_panel` for every t.

**Protected (Tier 1, never offered for relaxation)**

- C8. Comfort: `T_min <= T[t] <= T_max` for **t = 0..96**, including the final boundary state.

**Validation checks on the instance (fail loudly, do not solve)**

- `T_out[t] > T_min` for all t (cooling-only model cannot protect a lower bound otherwise), or the instance must add a heating mode.
- `a` and `b` are documented with units. `b` includes COP.

## 5. Objective

Primary: minimize modeled cost

```
cost = sum_t c[t] * dt * (p[t] + P_W*w[t] + P_H*h[t] + base_cost_term)
```

where `base_cost_term = base[t]` if `budget_scope = "total_home"`, otherwise 0.

Secondary (lexicographic tie-break, so replays are deterministic): fewest HVAC switches, then earliest EV charge completion.
Implementation: solve primary to optimality, add `cost <= opt_cost + epsilon_cents` as a constraint, then solve the secondary.

## 6. Constraint tiers and state

| Tier | Meaning | Relaxation |
| --- | --- | --- |
| 0 | Physical invariants (C1-C7) | never |
| 1 | Protected preferences (C8) | never offered |
| 2 | Firm commitment | only with explicit user authorization |
| 3 | Stated / negotiable goal | may be offered as a counteroffer |

State transitions:

- Initial request: `ev.deadline` is tier 3 (`stated`), in the `negotiable` list.
- User rejects an offered deadline change -> `ev.deadline` becomes tier 2 (`firm`) and is persisted.
- A firm constraint is a hard constraint in every solve and is **never** in a counteroffer.
- Budget and washer deadline stay tier 3 unless the user firms them.

Persisted record:

```
{ "key": "ev.deadline", "value": "07:00", "tier": "firm",
  "scope": "standing", "set_at": "<iso>", "source_utterance_id": "<id>" }
```

## 7. Solve pipeline

1. **Stage 0, physical feasibility (no budget).** Solve C1-C8. If infeasible, status `INFEASIBLE_PHYSICAL`.
   Diagnose by re-solving with each *negotiable* constraint (tier 3 only) relaxed, one at a time. Report which relaxations restore feasibility. Never relax tier 0 or 1, never invent a minimum.
2. **Stage 1, minimum cost.** Solve to optimality (gap 0 in tests). Output `min_cost`.
3. **Stage 2, compare.** If `min_cost <= budget`, return `OPTIMAL_WITHIN_BUDGET` with the plan. Otherwise `BUDGET_MISS`.
4. **Stage 3, counteroffers (only on BUDGET_MISS).** For each dimension allowed by tier and the `negotiable` list, run separate solves:
   - Raise budget: required budget is `min_cost`.
   - Extend EV deadline (only if tier 3): candidates `D_EV + 4*j`, j=1..J. Record `cost(D')`. Report the smallest extension reaching the budget, or the whole cost curve if none does.
   - Delay washer finish: same procedure over `D_W` candidates.
   - Widen comfort band: **not attempted**.
5. **Pareto filter.** Candidates are compared on (final cost, EV delay minutes, washer delay minutes). Drop dominated ones. Present at most 3.
6. **Cost-driving claim.** A constraint may be called cost-driving only if `cost(relaxed) < cost(original)` was computed. Otherwise say it is active, not cost-driving.
7. **If all permitted relaxations are exhausted or refused:** offer the proven-minimum plan with the overrun stated, or no action. Never silently change a firm constraint.

Per-solve time limit: 2 s. Run Stage 3 candidates in parallel. Solver: HiGHS (continuous temperature + binary variables). Fixed settings, single thread, fixed seed for replay.

## 8. I/O contract

Request (arrays abbreviated):

```json
{
  "request_id": "demo-001",
  "horizon_start": "2026-10-22T18:00:00",
  "slot_minutes": 15,
  "panel_limit_kw": 9.6,
  "tariff_dataset_id": "published-tariff-snapshot-v1",
  "tariff_usd_per_kwh": ["... 96 values ..."],
  "base_load_kw": ["... 96 values ..."],
  "outdoor_temp_c": ["... 97 values ..."],
  "ev": {
    "required_battery_energy_kwh": 24,
    "power_levels_kw": [0, 1.8, 3.6, 5.4, 7.2],
    "efficiency": 0.9,
    "available_from_slot": 8,
    "deadline_slot": 52,
    "deadline_tier": "stated"
  },
  "washer": {
    "power_kw": 2, "duration_slots": 6,
    "earliest_start_slot": 0, "must_finish_by_slot": 92
  },
  "hvac": {
    "power_kw": 3, "initial_temp_c": 24,
    "min_temp_c": 22, "max_temp_c": 25, "comfort_tier": "protected",
    "tau_hours": 6, "cooling_per_slot_c": 0.4,
    "min_on_slots": 2, "min_off_slots": 2
  },
  "budget_usd": 5,
  "budget_scope": "total_home",
  "negotiable": ["budget", "washer_deadline", "ev_deadline"]
}
```

(`tau_hours` and `cooling_per_slot_c` are placeholders to be calibrated and documented.)

Response:

- `status`: `OPTIMAL_WITHIN_BUDGET | BUDGET_MISS | INFEASIBLE_PHYSICAL | TIME_LIMIT | ERROR`
- `min_cost_usd`, `lower_bound_usd`, `gap`
- `schedule`: per-slot EV level, washer state, HVAC state, temperature, total load
- `constraint_report`: each constraint, satisfied or violated, with slack
- `counteroffers`: list of `{dimension, change, final_cost_usd, schedule_ref, replay_input}`
- `cost_driving`: list of constraints with computed cost deltas
- `persist`: decisions and preference updates to store
- `input_hash`, `output_hash` for replay

## 9. Test gates

**Gate A: solver (Oct 13).**

- A1. MILP optimum equals brute-force optimum on small instances (6-8 slots, 3 EV levels, short washer cycle, HVAC on/off). Compare in integer cents, MIP gap 0.
- A2. Combined load never exceeds 9.6 kW, base load included.
- A3. Washer runs exactly one uninterrupted cycle inside its window.
- A4. Temperature stays in the protected band for t=0..96. HVAC min on/off holds.
- A5. Physically impossible instance returns `INFEASIBLE_PHYSICAL` with diagnostics and no schedule.
- A6. Impossible budget returns `BUDGET_MISS`, and each counteroffer is re-solved and independently re-verified (cost, deadline, device limits).
- A7. Changing one constraint produces a different, valid plan.
- A8. Same input replays to the same output hash.

**Gate B: negotiation (Oct 16).**

- B1. A firm EV deadline survives a new session and is never offered for relaxation.
- B2. Every number in an LLM explanation exists in solver output (templated slots plus an automated numeric check).
- B3. Human approval triggers an MCP tool call that changes simulated device state. The call appears in the audit log.

**Cut-scope rule.** If Gate A is not green by end of Oct 13: one EV, one tariff, one negotiated deadline, no washer, no dashboard.

## 10. Open decisions (need an answer before coding)

1. `budget_scope`: total home or controllable devices only.
2. Persisted preference scope: standing until revoked, or "tomorrow only."
3. EV power levels (the set above is a placeholder).
4. Which published tariff to snapshot, and the demo scenario parameters. Say on screen that the scenario is constructed on real tariff data.
5. Thermal coefficients: calibrate and document, with units.
