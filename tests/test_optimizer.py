"""Owner: P1. El LP de 24 horas."""
import numpy as np

from battery import optimizer
from battery.optimizer import plan


def _case():
    price = np.r_[np.full(4, 0.05), np.full(4, 0.30), np.full(16, 0.10)]
    return dict(soc_kwh=0.0, load_kw=np.full(24, 1000.0), pv_kw=np.zeros(24), price=price, co2=price,
                w_co2=0.7, w_cost=0.3)


def test_charges_cheap_and_discharges_expensive():
    a = plan(**_case())
    assert (a[:4] > 0).any() and (a[4:8] < 0).any()
    assert np.abs(a).max() <= 500 + 1e-6


def test_keeps_charge_when_there_is_no_load_and_it_has_value():
    """Sin consumo no hay nada que ahorrar: si la carga tiene valor para después, el plan la guarda."""
    case = _case()
    case["soc_kwh"] = 2000.0
    case["load_kw"] = np.zeros(24)
    a = plan(terminal_value=0.05, **case)
    assert (a > -1e-6).all()


def test_only_buys_below_the_reserve_price():
    """Sin consumo en todo el horizonte, solo se carga en las horas que cuestan menos que el valor
    de la energía guardada (el precio de reserva), empezando por las más baratas."""
    case = _case()                                   # pesos: 0,05 (4 h), 0,30 (4 h) y 0,10 (16 h)
    case["load_kw"] = np.zeros(24)
    eta = 0.9 ** 0.5
    a = plan(terminal_value=0.08 / eta, **case)      # reserva 0,08: solo valen las horas de 0,05
    assert (a[:4] > 400).all() and np.abs(a[4:]).max() < 1e-6
    a = plan(terminal_value=0.04 / eta, **case)      # reserva 0,04: ninguna hora vale
    assert np.abs(a).max() < 1e-6


def test_falls_back_to_another_method(monkeypatch):
    """Si el método por defecto del solver falla, se prueba con los otros antes de rendirse."""
    real = optimizer.linprog
    calls = []

    def flaky(*args, method="highs", **kw):
        calls.append(method)
        if method == "highs":
            raise RuntimeError("fallo simulado")
        return real(*args, method=method, **kw)

    monkeypatch.setattr(optimizer, "linprog", flaky)
    a = plan(**_case())
    assert calls[:2] == ["highs", "highs-ds"] and (a[:4] > 0).any()
