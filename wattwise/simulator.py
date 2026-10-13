import asyncio
import json

from .client import call, connection
from .providers import provider
from .store import demo_now


async def main():
    request = "Charge my EV before 7 AM using the cheapest available electricity."
    intent = provider().parse(request, demo_now())
    async with connection() as session:
        prices = await call(session, "get_energy_prices")
        device = await call(session, "get_device_constraints")
        plan = await call(session, "optimize_schedule", {"deadline": intent.deadline.isoformat()})
        print(f"SIMULATION | {prices['dataset']} | {device['name']} | clock {demo_now().isoformat()}")
        print(json.dumps(plan, indent=2))
        approval = input(f"Apply plan {plan['plan_id']} to the simulated charger? Type APPLY to confirm: ")
        if approval != "APPLY":
            print("Cancelled. Nothing applied.")
            return
        print(json.dumps(await call(session, "apply_schedule", {"plan_id": plan["plan_id"], "confirmed": True}), indent=2))
        print(json.dumps(await call(session, "get_execution_history"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
