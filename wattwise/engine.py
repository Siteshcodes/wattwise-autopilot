"""Continuous, interruptible charging with constant power and hourly energy prices.

Greedy cheapest-first is optimal here: every kWh is interchangeable and each
interval has an independent capacity. No start costs, ramping, or demand charges.
"""
from datetime import timedelta
from decimal import Decimal

from .models import Device, DomainError, Schedule, Slot, Tariff


def schedule(device: Device, tariffs: list[Tariff], now, deadline, cheapest=True) -> Schedule:
    start = max(now, device.available_from)
    stop = min(deadline, device.available_until)
    if stop <= start:
        raise DomainError("INFEASIBLE", "Deadline leaves no available charging time.")
    intervals = []
    cursor = start
    for tariff in sorted(tariffs, key=lambda t: t.start):
        if tariff.end <= tariff.start:
            raise DomainError("INVALID_TARIFF", "Tariff interval must have positive duration.")
        a, b = max(start, tariff.start), min(stop, tariff.end)
        if a >= b:
            continue
        if a != cursor:
            raise DomainError("TARIFF_COVERAGE", "Tariffs contain a gap or overlap in the requested window.")
        intervals.append((a, b, tariff.price_per_kwh))
        cursor = b
    if cursor != stop:
        raise DomainError("TARIFF_COVERAGE", "Synthetic tariffs do not cover the requested window.")
    capacity = sum((Decimal(str((b-a).total_seconds())) / 3600 * device.max_power_kw for a,b,_ in intervals), Decimal(0))
    if capacity < device.required_kwh:
        raise DomainError("INFEASIBLE", f"Need {device.required_kwh} kWh, but only {capacity.normalize()} kWh can be delivered before the deadline at {device.max_power_kw} kW.")
    if cheapest:
        intervals.sort(key=lambda x: (x[2], x[0]))
    remaining = device.required_kwh
    slots = []
    for a, b, rate in intervals:
        energy = min(remaining, Decimal(str((b-a).total_seconds())) / 3600 * device.max_power_kw)
        if energy <= 0:
            break
        end = a + timedelta(seconds=float(energy / device.max_power_kw * 3600))
        slots.append(Slot(start=a, end=end, energy_kwh=energy, power_kw=device.max_power_kw, price_per_kwh=rate, cost=energy*rate))
        remaining -= energy
    slots.sort(key=lambda s: s.start)
    return Schedule(slots=slots, energy_kwh=device.required_kwh, cost=sum((s.cost for s in slots), Decimal(0)))
