"""Owner: P1. El agente completo: sin infracciones, mejor que no hacer nada y rápido."""
from battery.data import load, validation_split
from battery.params import N_STEPS, TIME_BUDGET_S
from battery.policy import BatteryAgent
from battery.sim import baseline_totals, score, simulate


def test_agent_one_week():
    df = validation_split(load()).iloc[:168].reset_index(drop=True)
    agent = BatteryAgent()
    res = simulate(agent, df)
    sc = score(res.totals, baseline_totals(df))
    assert sc["infractions"] == 0
    assert sc["score"] > 0
    assert agent.policy.n_fallbacks == 0
    projected = res.totals["runtime_s"] * N_STEPS / len(df)
    assert projected < TIME_BUDGET_S, f"proyección a 2.016 h: {projected:.1f} s"


def test_spends_battery_when_data_ends():
    """Con la previsión recortada (fin de los datos), la carga final no vale nada."""
    import numpy as np

    from battery.obs import Obs

    agent = BatteryAgent()
    full = Obs(12, 2, 1500.0, np.full(24, 0.1), np.full(24, 0.1), 900.0, 0.0)
    end = Obs(12, 2, 1500.0, np.full(3, 0.1), np.full(3, 0.1), 900.0, 0.0)
    assert not agent.policy.episode_ends_soon(full)
    assert agent.policy.episode_ends_soon(end)
    assert agent.policy.terminal_value(end, 3) == 0.0
    assert agent.policy.act_obs(end) < 0          # descarga lo que queda


def test_does_not_depend_on_episode_length():
    """El agente sigue planificando después de 2.016 pasos (no cuenta pasos)."""
    import numpy as np

    from battery.obs import Obs

    agent = BatteryAgent()
    agent.policy.t = 5000
    price = np.r_[np.full(4, 0.05), np.full(20, 0.30)]      # barato ahora, caro después
    obs = Obs(3, 2, 200.0, price, price, 900.0, 0.0)
    assert not agent.policy.episode_ends_soon(obs)
    assert agent.policy.act_obs(obs) > 0                    # carga para las horas caras


def test_no_discharge_into_dead_meter():
    """Si el contador marcó 0 la hora anterior, no se descarga (sería energía tirada)."""
    import numpy as np

    from battery.obs import Obs

    agent = BatteryAgent()
    price = np.r_[0.30, np.full(23, 0.05)]                  # solo esta hora es cara: el plan descarga ya
    normal = Obs(20, 2, 1500.0, price, price, 900.0, 0.0)
    dead = Obs(20, 2, 1500.0, price, price, 0.0, 0.0)
    assert agent.policy.act_obs(normal) < 0
    assert agent.policy.act_obs(dead) == 0.0


# ----------------------------------------------------------------- semanas sin datos de contador
def _obs_at(ts, load_prev, price=None, soc=1000.0):
    import numpy as np
    import pandas as pd

    from battery.obs import Obs

    ts = pd.Timestamp(ts)
    price = np.full(24, 0.1) if price is None else price
    return Obs(ts.hour, ts.dayofweek, soc, price, price, load_prev, 0.0, ts)


def test_block_tracking():
    """Contador a 0 desde la primera hora de una semana = semana sin datos; a media semana, avería corta."""
    from battery.policy import MPCPolicy

    pol = MPCPolicy()
    assert pol.track_block(_obs_at("2025-10-31 22:00", 900.0))            # primera observación: bloque nuevo
    assert not pol.track_block(_obs_at("2025-10-31 23:00", 900.0))
    assert pol.track_block(_obs_at("2025-11-24 00:00", 900.0))            # salto de fechas: semana nueva
    assert not pol.no_data_block
    assert not pol.track_block(_obs_at("2025-11-24 01:00", 0.0))          # la primera hora marcó 0
    assert pol.no_data_block
    pol.track_block(_obs_at("2025-11-24 02:00", 850.0))                   # vuelve la lectura
    assert not pol.no_data_block
    pol.track_block(_obs_at("2025-11-24 03:00", 0.0))                     # avería a media semana: corta
    assert not pol.no_data_block
    for h in range(4, 4 + 23):                                            # ...hasta que dura más de un día
        pol.track_block(_obs_at(f"2025-11-24 {h % 24:02d}:00" if h < 24 else f"2025-11-25 {h - 24:02d}:00", 0.0))
    assert pol.no_data_block


def test_reserve_weight_is_more_patient_with_more_days():
    from battery.policy import MPCPolicy

    pol = MPCPolicy()
    pol.valleys.extend([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    r = [pol.reserve_weight(d) for d in (1, 2, 4, 7)]
    assert r[0] == 4.0 and r[0] > r[1] > r[2] > r[3] > 1.0


def test_stale_reading_at_week_start_is_ignored():
    """En la primera hora de una semana, la lectura es de la semana anterior: un 0 no frena la descarga."""
    import numpy as np

    from battery.policy import MPCPolicy

    price = np.r_[0.30, np.full(23, 0.05)]            # solo esta hora es cara: toca descargar
    pol = MPCPolicy()
    pol.track_block(_obs_at("2025-11-30 23:00", 0.0))
    assert pol.act_obs(_obs_at("2025-12-25 00:00", 0.0, price, soc=1500.0)) < 0
    pol = MPCPolicy()
    pol.act_obs(_obs_at("2025-12-25 00:00", 900.0))
    assert pol.act_obs(_obs_at("2025-12-25 01:00", 0.0, price, soc=1500.0)) == 0.0   # misma semana: sí frena


def test_no_data_week_buys_late_and_never_dumps():
    """Semana entera con el contador a 0 (como noviembre): no tira energía, llega cargado a la semana
    siguiente y no lo hace peor que la lógica anterior (cargar en la primera hora barata)."""
    import pandas as pd

    from battery.policy import MPCPolicy

    val = validation_split(load())
    weeks = [val.iloc[i * 168:(i + 1) * 168].copy() for i in range(3)]
    for w, start in zip(weeks, ("2025-10-25", "2025-11-24", "2025-12-25")):   # calendario del test oficial
        w["timestamp"] = pd.date_range(start, periods=168, freq="h")
    weeks[1][["load_kw", "pv_kw"]] = 0.0
    df = pd.concat(weeks, ignore_index=True)

    class Old(MPCPolicy):                      # sin seguimiento de semanas: la lógica anterior
        def track_block(self, obs):
            return False

    class OldAgent:
        def __init__(self):
            self.policy = Old()

        def act(self, obs):
            return self.policy.act(obs)

    base = baseline_totals(df)
    new = simulate(BatteryAgent(), df)
    old = simulate(OldAgent(), df)
    s_new, s_old = score(new.totals, base), score(old.totals, base)
    zero = new.log.iloc[168:336]
    assert s_new["infractions"] == 0
    # En la primera hora todavía no se sabe que la semana viene sin datos; desde la segunda, nada
    # se descarga contra un consumo nulo.
    assert zero.export_kw.iloc[1:].sum() < 1e-6
    assert (zero.action_kw.iloc[1:] > -1e-6).all()
    assert zero.soc_kwh.iloc[-1] > 1500                    # llega cargado al 25 de diciembre
    assert s_new["score_raw"] >= s_old["score_raw"] - 1e-3


def test_no_data_in_the_last_week_buys_nothing():
    """Si la semana sin datos es la última del test (agosto de 2026), no hay semana siguiente
    para la que cargar: el agente no compra nada."""
    import pandas as pd

    val = validation_split(load())
    weeks = [val.iloc[i * 168:(i + 1) * 168].copy() for i in range(2)]
    for w, start in zip(weeks, ("2026-07-25", "2026-08-25")):
        w["timestamp"] = pd.date_range(start, periods=168, freq="h")
    weeks[1][["load_kw", "pv_kw"]] = 0.0
    df = pd.concat(weeks, ignore_index=True)
    res = simulate(BatteryAgent(), df)
    last = res.log.iloc[168:]
    assert res.totals["infractions"] == 0
    assert last.import_kw.iloc[1:].sum() < 1e-6          # desde que se sabe que no hay datos, no compra
    assert last.export_kw.iloc[1:].sum() < 1e-6
