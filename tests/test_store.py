from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from wattwise.store import Store, demo_now


def test_concurrent_apply_and_restart(tmp_path):
    path = str(tmp_path / "state.sqlite3")
    store = Store(path)
    plan = store.optimize("ev-1",demo_now()+timedelta(hours=11))
    with ThreadPoolExecutor(max_workers=4) as pool:
        actions = list(pool.map(lambda _: Store(path).apply(plan.plan_id,True),range(4)))
    assert len({a["execution_id"] for a in actions}) == 1
    restarted = Store(path)
    assert restarted.device().revision == 1
    assert len(restarted.history()) == 1
