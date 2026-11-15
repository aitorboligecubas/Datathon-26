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


def test_train_has_no_meter_before_the_november_week():
    """Un dato del train que usamos en la presentación: la semana de noviembre de 2025 es la única del
    calendario del test que empezaría justo después de 7 días sin una sola lectura del contador."""
    import pandas as pd
    import pytest

    from battery.data import TRAIN_DIR, ensure_official

    if not ensure_official():
        pytest.skip("sin datos oficiales")
    col = "Contador - POTENCIA ACTIVA EXPORTADA (kW)"
    meter = pd.read_csv(TRAIN_DIR / "contador.csv", usecols=["Fecha", col], parse_dates=["Fecha"])
    readings = meter.dropna(subset=[col]).Fecha
    silent = []
    for month in pd.period_range("2025-09", "2026-08", freq="M"):
        start = pd.Timestamp(month.year, month.month, month.days_in_month - 6)     # 00:00 del primer día del test
        before = readings[(readings >= start - pd.Timedelta(days=7)) & (readings < start)]
        if before.empty:
            silent.append((month.year, month.month))
    assert silent == [(2025, 11)]


def test_week_with_empty_readings_fills_the_battery_and_waits():
    """Si el contador no da ni un 0 (lectura vacía) desde la primera hora de una semana, el agente no
    descarga y deja la batería llena. Con lecturas normales no cambia nada."""
    import numpy as np

    from battery.policy import MPCPolicy

    price = np.r_[0.30, np.full(23, 0.05)]            # esta hora es la más cara: con consumo tocaría descargar
    nan = float("nan")
    pol = MPCPolicy()
    pol.act_obs(_obs_at("2026-01-25 00:00", 900.0, price, soc=1000.0))
    a = pol.act_obs(_obs_at("2026-01-25 01:00", nan, price, soc=1000.0))
    assert pol.no_data_block and pol.no_reading and a > 499.0
    assert pol.act_obs(_obs_at("2026-01-25 02:00", nan, price, soc=1999.0)) < 2.0       # llena: espera
    assert pol.act_obs(_obs_at("2026-01-25 03:00", 900.0, price, soc=2000.0)) < 0       # vuelve la lectura
    assert not pol.no_data_block and not pol.no_reading


# ------------------------------------------------------------------------------------------- modo difícil
def _hard_obs(ts, soc, load_prev=900.0, pv_prev=0.0, price=(0.10, 0.10, 0.10), co2=(0.10, 0.10, 0.10)):
    """Observación del modo difícil tal como la da el entorno: 3 horas de precio y CO2 y la batería grande."""
    import pandas as pd

    ts = pd.Timestamp(ts)
    return {"timestamp": ts, "hour": int(ts.hour), "day_of_week": int(ts.dayofweek), "soc_kwh": float(soc),
            "soc_pct": float(soc) / 6000.0, "preu_actual": float(price[0]), "co2_actual": float(co2[0]),
            "preus_properes_24h": [float(v) for v in price], "co2_properes_24h": [float(v) for v in co2],
            "noves_dades_5min": {"ultim_consum_kw": load_prev, "ultima_solar_kw": pv_prev},
            "cap_max_kwh": 6000.0, "power_max_kw": 1500.0}


def _hard_run(agent, df):
    """Simula el modo difícil con la física del entorno. Devuelve (totales, kWh vertidos al descargar)."""
    from battery.hard import HARD_PARAMS as p
    from battery.sim import apply_action

    soc, infr, co2, cost, spilled = p.soc_init_kwh, 0, 0.0, 0.0, 0.0
    for t in range(len(df)):
        row, prev = df.iloc[t], df.iloc[max(t - 1, 0)]
        obs = _hard_obs(row.timestamp, soc, float(prev.load_kw), float(prev.pv_kw),
                        df.price_eur_kwh.iloc[t:t + 3].tolist(), df.co2_kg_kwh.iloc[t:t + 3].tolist())
        action, soc, bad = apply_action(soc, float(agent.act(obs)), p)
        infr += bad
        grid = row.load_kw - row.pv_kw + action
        co2 += max(grid, 0.0) * row.co2_kg_kwh
        cost += max(grid, 0.0) * row.price_eur_kwh
        if action < 0:
            spilled += max(-grid, 0.0)
    return {"co2_kg": co2, "cost_eur": cost, "infractions": infr}, spilled


def _hard_frame(start, days):
    """Unos días del train con la solar del modo difícil (x12)."""
    df = load()
    df = df[df.timestamp >= start].iloc[:24 * days].reset_index(drop=True).copy()
    df["pv_kw"] = df["pv_kw"] * 12.0
    return df


def test_hard_agent_saves_without_infractions():
    """Cuatro días de mayo (con excedente solar a mediodía): ahorra, no infringe, no cae en el respaldo y no
    tira la batería descargando por encima del consumo."""
    from battery.hard import HardBatteryAgent

    df = _hard_frame("2026-05-11", 4)
    agent = HardBatteryAgent()
    totals, spilled = _hard_run(agent, df)
    sc = score(totals, baseline_totals(df))
    assert sc["infractions"] == 0
    assert sc["score"] > 5.0
    assert agent.policy.n_fallbacks == 0
    assert spilled < 0.05 * 6000.0 * len(df) / 24, f"vertido al descargar: {spilled:.0f} kWh"


def test_hard_uses_the_extended_tables_and_falls_back_without_them():
    """Con las tablas ampliadas en models/hard_solar.json se usa el previsor ampliado; si faltan o están rotas,
    el sencillo. En ningún caso se lanza un error."""
    from battery.forecaster import Forecaster
    from battery.hard import HardPolicy
    from battery.hard_solar import NetLoadForecaster, SolarCand, make_netload

    assert isinstance(HardPolicy().netload, SolarCand)
    for prior in (None, {}, {"cand": {}}, {"cand": {"pv_clear": [[1.0]]}}, {"cand": "roto"}):
        assert isinstance(make_netload(prior, Forecaster(None)), NetLoadForecaster)


def test_hard_does_not_discharge_into_a_dead_meter():
    """Contador a 0 y sin solar: descargar sería tirar la energía, por cara que sea la hora."""
    from battery.hard import HardPolicy

    pol = HardPolicy()
    dear = (0.40, 0.05, 0.05)
    assert pol.act(_hard_obs("2026-01-27 18:00", 3000.0, 900.0, 0.0, dear, dear)) <= 0
    assert pol.act(_hard_obs("2026-01-27 19:00", 3000.0, 900.0, 0.0, dear, dear)) < 0      # con consumo, descarga
    assert pol.act(_hard_obs("2026-01-27 20:00", 3000.0, 0.0, 0.0, dear, dear)) >= 0       # contador caído: no


def test_hard_plans_across_months_and_ends_in_august():
    """El test son los últimos 7 días de cada mes, uno detrás de otro, y acaba el 31/08/2026."""
    import pandas as pd

    from battery.hard import HardPolicy

    pol = HardPolicy()
    times = pol.horizon_times(_obs_at("2026-07-31 22:00", 900.0))
    assert len(times) == 24 and times[2] == pd.Timestamp("2026-08-25 00:00")
    assert len(pol.horizon_times(_obs_at("2026-08-31 22:00", 900.0))) == 2
    assert pol.act(_hard_obs("2026-08-31 23:00", 3000.0, 900.0, 0.0)) < 0        # última hora: gasta lo que queda


def test_hard_detects_weekly_resets_and_restarts():
    """Si la segunda semana empieza con la batería al 50 % y no como él la dejó, cada semana es una simulación
    aparte y se cierra vacía. Si el reloj vuelve atrás, empieza otra simulación: se olvida lo deducido."""
    from battery.hard import HardPolicy

    pol = HardPolicy()
    pol.act(_hard_obs("2025-09-30 22:00", 5000.0))
    pol.act(_hard_obs("2025-09-30 23:00", 5000.0))
    assert abs(pol.expected_soc - 3000.0) > 1.0
    pol.act(_hard_obs("2025-10-25 00:00", 3000.0))                 # 50 % justo, y no es lo que dejó
    assert pol.n_blocks == 2 and pol.empty_weeks
    assert len(pol.horizon_times(_obs_at("2025-10-31 22:00", 900.0))) == 2
    pol.act(_hard_obs("2025-09-24 00:00", 3000.0))                 # el reloj vuelve atrás
    assert pol.n_blocks == 1 and not pol.empty_weeks

    pol = HardPolicy()                                             # sin reinicio: la batería sigue
    pol.act(_hard_obs("2025-09-30 22:00", 5000.0))
    pol.act(_hard_obs("2025-09-30 23:00", 5000.0))
    pol.act(_hard_obs("2025-10-25 00:00", pol.expected_soc))
    assert pol.n_blocks == 2 and not pol.empty_weeks


def test_plan_with_uncertainty_discharges_more_when_stored_energy_is_cheap():
    """El plan con incertidumbre: cada kW adicional de descarga tiene menos probabilidad de aprovecharse. Si lo
    guardado no vale nada se apura hasta el cuantil más alto del consumo neto; si vale casi como esta hora, solo
    se descarga lo seguro. Nunca se descarga por encima del cuantil más alto."""
    import numpy as np

    from battery.hard import HARD_PARAMS as p
    from battery.hard import plan_scen
    from battery.hard_solar import scen_probs

    tail, head = scen_probs((0.2, 0.5, 0.8))                 # P(consumo neto > tramo) = 1,00 / 0,65 / 0,35
    assert np.allclose(tail, [1.0, 0.65, 0.35]) and np.allclose(head, [0.0, 0.35, 0.65, 1.0])
    nodes = np.array([[200.0, 600.0, 1000.0]])
    for stored_value, expected in ((0.0, -1000.0), (0.5, -600.0), (0.9, -200.0), (1.1, 0.0)):
        a = plan_scen(3000.0, nodes, tail, head, np.array([1.0]), stored_value * p.eta_discharge, p)
        assert abs(a[0] - expected) < 1e-6, (stored_value, a)
    # Con excedente incierto (consumo neto negativo): se carga gratis lo seguro y se paga la parte dudosa solo si compensa.
    surplus = np.array([[-900.0, -500.0, -100.0]])
    for stored_value, expected in ((0.01, 100.0), (0.5, 500.0), (0.9, 900.0)):
        a = plan_scen(0.0, surplus, tail, head, np.array([1.0]), stored_value / p.eta_charge, p)
        assert abs(a[0] - expected) < 1e-6, (stored_value, a)


def test_hard_uses_the_uncertainty_plan_and_falls_back_without_its_table():
    """Con la tabla de cuantiles en models/hard_solar.json decide el plan con incertidumbre; sin ella (o apagado),
    el plan de margen fijo de las versiones anteriores. En los dos casos, sin infracciones ni errores."""
    from battery.hard import HardBatteryAgent

    df = _hard_frame("2026-05-11", 2)
    agent = HardBatteryAgent()
    assert agent.policy.netload.scen_ok
    totals, _ = _hard_run(agent, df)
    assert totals["infractions"] == 0 and agent.policy.n_scen == len(df) and agent.policy.n_fallbacks == 0

    for broken in ("apagado", "sin tabla"):
        agent = HardBatteryAgent()
        if broken == "apagado":
            agent.policy.use_scenarios = False
        else:
            agent.policy.netload.set_scenarios({"alphas": [0.5], "u": [float("nan")]})
            assert not agent.policy.netload.scen_ok
        totals, _ = _hard_run(agent, df)
        assert totals["infractions"] == 0 and agent.policy.n_scen == 0 and agent.policy.n_fallbacks == 0


def test_market_profile_is_interpolated_between_months():
    """El perfil de precio y CO2 se interpola entre meses según el día: en el centro de los datos del mes es el del
    mes; a final de mes (los días del test) está a medio camino del mes siguiente; sin centros, el del mes tal cual."""
    import numpy as np
    import pandas as pd

    from battery.hard_market import MarketForecaster, month_blend

    centers = [12.5] * 12
    assert month_blend(3, 12.5, centers) == (3, 0.0)                       # centro del mes: sin mezcla
    other, w = month_blend(3, 28.0, centers)                               # 28 de marzo: hacia abril
    assert other == 3 and 0.45 < w < 0.56
    other, w = month_blend(1, 2.0, centers)                                # 2 de enero: hacia diciembre
    assert other == 11 and 0.3 < w < 0.4
    assert month_blend(12, 31.0, centers)[0] == 0                          # diciembre mira a enero

    prof = np.zeros((12, 3, 24))
    for mo in range(12):
        prof[mo] = 0.10 + 0.01 * mo                                        # marzo 0,12; abril 0,13
    prior = {"price": prof.tolist(), "co2": prof.tolist(), "day_center": centers}
    f = MarketForecaster(prior)
    assert abs(f.profile("price", pd.Timestamp("2026-03-12 12:00")) - 0.12) < 2e-4
    late = f.profile("price", pd.Timestamp("2026-03-28 12:00"))
    assert 0.1245 < late < 0.1256
    plain = MarketForecaster({"price": prof.tolist(), "co2": prof.tolist()})
    assert abs(plain.profile("price", pd.Timestamp("2026-03-28 12:00")) - 0.12) < 1e-12
    broken = MarketForecaster({"price": prof.tolist(), "co2": prof.tolist(), "day_center": [0.0] * 12})
    assert broken.centers is None and abs(broken.profile("price", pd.Timestamp("2026-03-28 12:00")) - 0.12) < 1e-12
