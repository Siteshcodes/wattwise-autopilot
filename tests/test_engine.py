from datetime import datetime, timedelta
from decimal import Decimal
from itertools import product

import pytest

from wattwise.engine import schedule
from wattwise.models import Device, DomainError, Tariff

NOW = datetime.fromisoformat("2026-10-12T20:00:00+05:30")


def fixtures(rates=(12,11,10,8,6,4,3,2,5,7,9), energy="21", power="7"):
    d = Device(available_from=NOW, available_until=NOW+timedelta(hours=len(rates)), required_kwh=energy, max_power_kw=power)
    tariffs = [Tariff(start=NOW+timedelta(hours=i), end=NOW+timedelta(hours=i+1), price_per_kwh=rate) for i,rate in enumerate(rates)]
    return d, tariffs


def test_demo_costs():
    d,t = fixtures()
    optimized = schedule(d,t,NOW,d.available_until)
    baseline = schedule(d,t,NOW,d.available_until,False)
    assert optimized.cost == 63
    assert baseline.cost == 231
    assert baseline.cost-optimized.cost == 168
    assert [s.start.hour for s in optimized.slots] == [1,2,3]


def test_partial_interval_and_deadline():
    d,t = fixtures((9,2,5), "8", "7")
    now = NOW+timedelta(minutes=30)
    deadline = NOW+timedelta(hours=2,minutes=15)
    result = schedule(d,t,now,deadline)
    assert result.cost == 19
    assert sum(s.energy_kwh for s in result.slots) == 8
    assert all(now <= s.start < s.end <= deadline for s in result.slots)
    assert all(abs(Decimal(str((s.end-s.start).total_seconds()))/3600*s.power_kw-s.energy_kwh) < Decimal("0.000001") for s in result.slots)


def test_matches_exhaustive_oracle():
    for rates in product((-2,0,3), repeat=3):
        d,t = fixtures(rates, "3", "2")
        optimum = min(sum(Decimal(e)*r for e,r in zip(allocation,rates)) for allocation in product(range(3),repeat=3) if sum(allocation)==3)
        assert schedule(d,t,NOW,d.available_until).cost == optimum


def test_infeasible_and_missing_prices():
    d,t = fixtures()
    with pytest.raises(DomainError, match="only 7"):
        schedule(d,t,NOW,NOW+timedelta(hours=1))
    with pytest.raises(DomainError, match="gap or overlap"):
        schedule(d,t[1:],NOW,d.available_until)
    with pytest.raises(DomainError, match="no available"):
        schedule(d,t,NOW,NOW)


def test_availability_intersection_and_ties():
    d,t = fixtures((1,1,1), "7")
    d.available_from = NOW+timedelta(hours=1)
    result = schedule(d,t,NOW,d.available_until)
    assert result.slots[0].start == d.available_from
