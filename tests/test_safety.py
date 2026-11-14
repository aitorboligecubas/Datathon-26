"""Owner: P1. Cero infracciones pase lo que pase."""
import numpy as np

from battery.params import DEFAULT_PARAMS as P
from battery.safety import clip_action, is_infraction, soc_after


def test_clip_never_infraction():
    rng = np.random.default_rng(0)
    for _ in range(20000):
        soc = float(rng.uniform(0, P.capacity_kwh))
        a = float(rng.normal(0, 2000))
        c = clip_action(a, soc)
        assert not is_infraction(c, soc)
        assert abs(c) <= 500.0
        assert 0.0 <= soc_after(soc, c) <= P.capacity_kwh


def test_clip_edges_and_garbage():
    assert clip_action(float("nan"), 1000) == 0.0
    assert clip_action(float("inf"), 1000) == 0.0
    assert clip_action("basura", 1000) == 0.0
    assert clip_action(100, P.capacity_kwh) == 0.0      # llena: no carga
    assert clip_action(-100, 0.0) == 0.0                # vacía: no descarga
    assert not is_infraction(clip_action(1e9, 1999.99), 1999.99)
