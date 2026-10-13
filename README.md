# WattWise

A working local vertical slice: request → deadline → real MCP Streamable HTTP tools → deterministic optimization → review → explicit approval → simulated charger → SQLite execution history → Next.js dashboard.

**No live tariffs, physical charger, or Alexa+ connection.** Bedrock is an optional intent parser; it never calculates prices or authorizes actions.

## Setup (Windows PowerShell)

Requirements: Python **3.12**, Node **22+**, npm. Tested here with Python 3.12 and Node 24.19.0. Run backend commands from the repository root.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python -m pip install -e ".[test]"
Copy-Item .env.example .env
cd web
npm ci
cd ..
```

`requirements-lock.txt` records the tested Windows dependency environment. On Linux/macOS, use `python3.12 -m venv .venv`, `.venv/bin/python -m pip install -e '.[test]'`, and `cp .env.example .env` instead. Use `.venv/bin/python` in the following commands. The Python project pins its direct dependencies; the npm lockfile pins the frontend dependency tree.

Start three terminals:

```powershell
# Terminal 1, repository root — MCP endpoint http://127.0.0.1:8000/mcp
.\.venv\Scripts\python -m wattwise.server
```

```powershell
# Terminal 2, repository root — dashboard gateway
.\.venv\Scripts\python -m uvicorn wattwise.api:app --host 127.0.0.1 --port 8001
```

```powershell
# Terminal 3
cd web
npm run dev
```

Open <http://127.0.0.1:3000>. Python processes load the root `.env`. The Next.js gateway uses `http://127.0.0.1:8001` by default; to override it, set `WATTWISE_API_URL` in `web/.env.local` or the frontend shell.

## Reproducible demo

The simulated clock is **12 October 2026, 20:00 IST**. The charger is available until **13 October, 07:00 IST**, needs **21 kWh**, and accepts up to **7 kW**. Each price below covers one hour starting at the listed time; these are deliberately synthetic **INR/kWh** prices.

| Start (IST) | 20:00 | 21:00 | 22:00 | 23:00 | 00:00 | 01:00 | 02:00 | 03:00 | 04:00 | 05:00 | 06:00 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| INR/kWh | 12 | 11 | 10 | 8 | 6 | 4 | 3 | 2 | 5 | 7 | 9 |

1. Submit **“Charge my EV before 7 AM using the cheapest available electricity.”**
2. Review both schedules. Immediate baseline: 20:00–23:00, `7 × (12+11+10) = ₹231`. Optimized: 01:00–04:00, `7 × (4+3+2) = ₹63`.
3. Confirm savings of **₹168 (72.73%)**. Before confirmation, the charger has no active plan and execution history is empty.
4. Click **Confirm & apply schedule**. The charger now holds the approved schedule, and the execution log contains both schedules, prices, confirmation, and calculations.
5. Reload the page or restart the backend: the action remains in SQLite.

Alternative terminal simulator, with the MCP server running:

```powershell
.\.venv\Scripts\python -m wattwise.simulator
```

It shows the proposal and waits for the exact text `APPLY`; any other response cancels. There is deliberately no automatic approval flag.

Try **“Charge my EV before 9 PM”** on an unused demo database: the system explains that only 7 kWh can fit before that deadline. Unsupported or ambiguous requests are rejected by the default parser.

One charger accepts one approved schedule per demo database. To repeat the scenario without deleting history, stop both Python servers, set `WATTWISE_DB=data/demo-2.sqlite3` in `.env` (choose a new filename), then restart them. A changed demo clock also requires a new database. The dashboard's scenario labels assume the default clock.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pip check
cd web
npm run typecheck
npm run build
```

Tests start real MCP servers as subprocesses on temporary loopback ports and use isolated SQLite databases. They cover initialization with **2025-11-25**, HTTP session headers, `tools/list`, input and output schemas, every tool, malformed inputs, missing devices/plans, infeasibility, unapproved execution, idempotency, stale plans, concurrent retries, persisted state, and gateway-to-MCP execution. Engine tests compare the greedy result with an independent exhaustive oracle over small cases, including negative prices, partial slots, and availability intersections. Provider tests use explicitly labeled stubs; these do **not** verify AWS connectivity.

Verified on 12 October 2026: **13 pytest tests passed**, `pip check` passed, TypeScript checking passed, and the Next.js **16.3.8** production build passed. A browser check against the production build verified planning, cancellation, explicit approval, the execution log, and persistence after reload, using a separate `data/browser-check.sqlite3` database. The untouched default database is available for your demo. Browser microphone capture was not exercised. [Browser verification screenshot](docs/browser-verified.jpg).

## Design and constraints

```
Next.js dashboard → same-origin Next.js route → Python gateway
                                               ↓ MCP SDK / Streamable HTTP
CLI simulator ───────────────────────────────→ FastMCP server
                                               ↓
                                        optimizer + SQLite
```

- FastMCP **2.14.5** and MCP Python SDK **1.26.0** are intentionally pinned and tested together for protocol **2025-11-25**. They are not claims about the newest release. The client rejects another negotiated revision.
- Typed Pydantic inputs and nested output schemas describe every tool. Successful calls and domain errors return `{ok, code, message, data}` in MCP `structuredContent`. Invalid schema inputs use MCP `isError` tool responses.
- `get_energy_prices()` reads seeded tariffs. `get_device_constraints(device_id)` reads persistent state. `optimize_schedule(deadline, device_id)` persists a proposal only. `apply_schedule(plan_id, confirmed)` applies an immutable stored proposal. `get_execution_history(limit)` returns full execution records.
- Cheapest-first allocation is optimal for this model: divisible energy, interruptible charging, constant maximum power, no ramp costs or minimum session length, flat per-kWh price per interval, and 100% charging efficiency. Intervals are clipped to availability, deadline, and demo time. Missing/overlapping prices are errors; infeasibility is never replaced by a fabricated schedule.
- Immediate baseline starts at the later of demo time and device availability, charges at maximum power continuously, and stops as soon as the required energy is delivered. Both schedules have the same constraints and energy requirement.
- Decimal arithmetic is used for energy and money. Values cross JSON as decimal strings; the UI rounds money only for display. Timestamp precision is microseconds. Percentage savings is defined only for a positive baseline cost; otherwise it is reported as zero while absolute savings remains valid.
- Application is atomic in a SQLite transaction, checks the device revision, and is idempotent by proposal ID. It stores a schedule on the simulated charger; it does not claim that electricity has already been delivered. Execution records retain the original proposal as reviewed, including its `awaiting_confirmation` proposal status; the enclosing execution is `scheduled` and `confirmed`.
- The dashboard requires an explicit click and a proposal-bound random confirmation token. Speech recognition can fill the transcript only; neither speech nor the provider can approve. The CLI requires `APPLY`.
- This is a **trusted, local, single-user demo**, bound to loopback, without authentication. The MCP tool's `confirmed=true` is an assertion by a trusted client that human consent was collected, not cryptographic proof of a human gesture. Do not connect an autonomous client that invents consent. Production identity, per-user authorization, and secure remote hosting are not implemented. Gateway tokens are in memory and reset on gateway restart; users must review again. Approved executions remain persisted.

## Amazon Bedrock

The adapter calls `boto3.client('bedrock-runtime').converse(...)` to parse an intent. It validates the returned deadline and never silently falls back if AWS fails. A model/profile ID is configuration, not guessed. Use an accessible Converse-compatible model with system messages and temperature support.

```powershell
$env:AWS_PROFILE = "your-configured-profile"
$env:AWS_DEFAULT_REGION = "us-east-1"
$env:BEDROCK_MODEL_ID = "your-accessible-model-or-inference-profile-id"
.\.venv\Scripts\python -m wattwise.bedrock_check
```

Only `LIVE BEDROCK CONVERSE SUCCEEDED` confirms an actual validated API response. Then set `WATTWISE_PROVIDER=bedrock` in `.env` and restart the gateway. AWS credentials follow the standard boto3 provider chain. The call requires `bedrock:InvokeModel` access. Credentials and a model ID were unavailable during development, so **live AWS integration remains unverified**.

## Functionality status

| Real and verified locally | Explicitly simulated | Not yet implemented / not verified |
|---|---|---|
| MCP HTTP transport and protocol negotiation | One driveway EV charger | Alexa+ registration, discovery, deployment, certification |
| Deterministic constrained optimization and cost baseline | Synthetic hourly tariff dataset | Live utility data, physical charger APIs |
| SQLite state, atomic execution, history | Fixed demo clock | Wall-clock scheduler, energy delivery, telemetry |
| CLI and dashboard review/confirmation flow | Browser voice transcript as input where supported | Browser microphone capture not verified in automated tests |
| Bedrock adapter contract tests | Stubbed Bedrock unit responses | Live Bedrock call, AWS hosting, AWS Builder eligibility |
| Next.js UI connected through the MCP gateway | Single device scenario | Multi-device coordination, battery losses, solar, demand charges |

No hackathon submission or track eligibility is claimed. This is a local foundation for an Alexa+ integration, not an Alexa+ integration itself.

## References used for compatibility

- [MCP 2025-11-25 transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [FastMCP HTTP server](https://gofastmcp.com/deployment/running-server)
- [Amazon Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
