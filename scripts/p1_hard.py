"""Banco de pruebas del HARD MODE. NO se empaqueta.

Owner: P1. Simula el modo difícil con los datos del train tal como lo describe la organización (Discord,
sábado 14/11 16:33): solar x12, batería de 6.000 kWh y ±1.500 kW, precio y CO2 conocidos solo 3 horas, y la
meteo de la hora anterior en `noves_dades_5min`.

    python scripts/p1_hard.py --split dev     # comparativa en los días 8-14 de cada mes (para diseñar)
    python scripts/p1_hard.py                 # en las últimas 168 h de cada mes (RESERVADA para verificar)
    python scripts/p1_hard.py --split dev --market scripts/p1_lab/hard_market_a.py:make   # probar un candidato
    python scripts/p1_hard.py --fit           # regenera models/hard_market.json con todo el train
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from battery.adapter import from_official  # noqa: E402
from battery.baselines import OracleAgent  # noqa: E402
from battery.data import TRAIN_DIR, ensure_official, load, train_split, validation_split  # noqa: E402
from battery.hard import HARD_PARAMS, HardPolicy  # noqa: E402
from battery.hard_market import KNOWN_HOURS, NATIONAL_HOLIDAYS, MarketCand, MarketForecaster  # noqa: E402
from battery.hard_solar import PV_FACTOR  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.safety import clip_action  # noqa: E402
from battery.sim import apply_action, baseline_totals, score  # noqa: E402

METEO_COLS = {"Atersa - IRRADIANCIA (W/m2)": "irradiancia_wm2",
              "Atersa - TEMPERATURA AMBIENTE (SENSOR 1) (ºC)": "temp_ambient_c",
              "Atersa - TEMPERATURA PANEL (SENSOR 1) (ºC)": "temp_panel_c",
              "Atersa - VELOCIDAD VIENTO (SENSOR 1) (m/s)": "vent_ms"}
MODELS = REPO / "models"


def hard_table() -> pd.DataFrame:
    """Tabla horaria del modo difícil: la estándar con la solar x12 y la meteo horaria."""
    ensure_official()
    df = load().copy()
    df["pv_kw"] = df["pv_kw"] * PV_FACTOR
    met = pd.read_csv(TRAIN_DIR / "meteo.csv", usecols=["Fecha"] + list(METEO_COLS), parse_dates=["Fecha"])
    met = met.set_index("Fecha").rename(columns=METEO_COLS).resample("1h").mean()
    return df.merge(met, left_on="timestamp", right_index=True, how="left")


def market_frame() -> pd.DataFrame:
    """Precio y CO2 horarios del train (todos los meses, noviembre incluido)."""
    pr = pd.read_csv(TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co = pd.read_csv(TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    m = pd.DataFrame({"price": pr.precio_eur_per_kwh, "co2": co.co2_kg_per_kwh}).dropna()
    return m[m.index < "2026-09-01"]


def market_types(index) -> np.ndarray:
    """Tipo de día de cada hora, como battery.hard_market.market_day_type (festivo nacional = domingo)."""
    t = np.where(index.dayofweek < 5, 0, np.where(index.dayofweek == 5, 1, 2))
    hol = np.array([(y, mo, d) in NATIONAL_HOLIDAYS for y, mo, d in zip(index.year, index.month, index.day)])
    return np.where(hol, 2, t)


def fit_market(exclude=None, refs_df: pd.DataFrame = None) -> dict:
    """Perfil de precio y CO2 por mes, tipo de día (laborable, sábado, domingo) y hora."""
    m = market_frame()
    if exclude is not None:
        m = m[~m.index.isin(exclude)]
    out = {}
    typ = market_types(m.index)
    for name in ("price", "co2"):
        g = m.groupby([m.index.month, typ, m.index.hour])[name].mean()
        by_h = m.groupby([m.index.month, m.index.hour])[name].mean()
        arr = np.full((12, 3, 24), np.nan)
        for mo in range(1, 13):
            for t in range(3):
                for h in range(24):
                    v = g.get((mo, t, h), np.nan)
                    arr[mo - 1, t, h] = v if np.isfinite(v) else by_h.get((mo, h), np.nan)
        out[name] = arr.tolist()
    out["reg"] = fit_market_regression(m, out)
    out["cand"] = fit_market_memory(exclude)
    if refs_df is not None:
        b = baseline_totals(refs_df)
        out["co2_ref_kg_per_h"] = b["co2_kg"] / len(refs_df)
        out["cost_ref_eur_per_h"] = b["cost_eur"] / len(refs_df)
    return out


def fit_market_memory(exclude=None) -> dict:
    """Tablas del previsor con memoria del train (13 pistas y los últimos 7 días de cada mes como "semilla").
    El ajuste está en scripts/p1_lab/hard_market_cand.py (fit_cand), que es donde se diseñó."""
    lab = str(REPO / "scripts" / "p1_lab")
    if lab not in sys.path:
        sys.path.insert(0, lab)
    from hard_market_cand import fit_cand
    return fit_cand(exclude)


def fit_market_regression(m: pd.DataFrame, prof: dict) -> dict:
    """Para cada antelación k = 3..23, regresión de la desviación futura z(t+k) = log(real/perfil) sobre
    las tres horas conocidas, la media de las últimas 6 y 24 horas y la de ayer a la misma hora ("full"),
    y otra solo con las tres horas conocidas para el arranque de cada semana ("cold").
    `m`: precio y CO2 horarios con los que se ajusta (ya sin las horas excluidas)."""
    typ = market_types(m.index)
    reg = {}
    for name in ("price", "co2"):
        p = np.asarray(prof[name])[m.index.month - 1, typ, m.index.hour]
        z = pd.Series(np.log(np.clip(m[name].to_numpy(), 1e-6, None) / np.clip(p, 1e-6, None)), index=m.index)
        full_idx = pd.date_range(m.index.min(), m.index.max(), freq="h")
        z = z.reindex(full_idx)                                   # los huecos (otras semanas, horas excluidas) quedan en NaN
        feats = pd.DataFrame({"z0": z, "z1": z.shift(-1), "z2": z.shift(-2),
                              "zm24": z.rolling(24, min_periods=12).mean(), "zm6": z.rolling(6, min_periods=3).mean()})
        full, cold = [], []
        for k in range(3, 24):
            d = pd.concat([feats, z.shift(24 - k).rename("zy"), z.shift(-k).rename("y")], axis=1)
            same_month = (d.index + pd.Timedelta(hours=k)).month == d.index.month
            dw = d[same_month].dropna()
            A = np.c_[dw[["z0", "z1", "z2", "zm24", "zm6", "zy"]].to_numpy(), np.ones(len(dw))]
            full.append([float(v) for v in np.linalg.lstsq(A, dw.y.to_numpy(), rcond=None)[0]])
            dc = d[same_month][["z0", "z1", "z2", "y"]].dropna()
            A = np.c_[dc[["z0", "z1", "z2"]].to_numpy(), np.ones(len(dc))]
            cold.append([float(v) for v in np.linalg.lstsq(A, dc.y.to_numpy(), rcond=None)[0]])
        reg[name] = {"full": full, "cold": cold}
    return reg


def fit_solar(table: pd.DataFrame) -> dict:
    """Tablas para la previsión de solar y consumo: cielo despejado (percentil 90) y media de la solar
    por mes y hora, y error típico del consumo neto de la hora actual por hora del día."""
    t = table.sort_values("timestamp").reset_index(drop=True)
    m, h = t.timestamp.dt.month, t.timestamp.dt.hour
    clear = np.zeros((12, 24)); mean = np.zeros((12, 24))
    gq = t.groupby([m, h]).pv_kw.quantile(0.9); gm = t.groupby([m, h]).pv_kw.mean()
    for mo in range(1, 13):
        for hh in range(24):
            clear[mo - 1, hh] = gq.get((mo, hh), np.nan); mean[mo - 1, hh] = gm.get((mo, hh), np.nan)
    for arr in (clear, mean):       # meses sin datos (noviembre): media de los vecinos
        for mo in range(12):
            if not np.isfinite(arr[mo]).all():
                a, b = arr[(mo - 1) % 12], arr[(mo + 1) % 12]
                arr[mo] = np.where(np.isfinite(a) & np.isfinite(b), (a + b) / 2, np.where(np.isfinite(a), a, b))
        arr[~np.isfinite(arr)] = 0.0
    # error de la previsión de la hora actual (misma receta que battery.hard_solar), por hora del día
    how = t.timestamp.dt.dayofweek * 24 + h
    prof = t.groupby(how).load_kw.mean()
    ok = t.timestamp.diff() == pd.Timedelta(hours=1)
    cl = pd.Series(clear[m.to_numpy() - 1, h.to_numpy()], index=t.index); mn = pd.Series(mean[m.to_numpy() - 1, h.to_numpy()], index=t.index)
    typical = (mn / cl).where(cl > 0, 0.0)
    c = (t.pv_kw.shift(1) / cl.shift(1)).clip(0, 1.5).where(cl.shift(1) >= 30)
    c = c.ffill().fillna(typical)
    pv_hat = cl * (typical + (c - typical) * 0.85)
    p_now = how.map(prof); p_prev = how.shift(1).map(prof)
    load_hat = p_now * (1 + ((t.load_kw.shift(1) / p_prev).clip(0.3, 3.0) - 1) * 0.9)
    err = ((t.load_kw - t.pv_kw) - (load_hat - pv_hat))[ok]
    sd = err.groupby(h[ok]).std().reindex(range(24)).fillna(err.std()).clip(lower=15.0)
    return {"pv_clear": clear.tolist(), "pv_mean": mean.tolist(), "net_sd": [float(v) for v in sd],
            "cand": fit_solar_tables(table)}


def fit_solar_tables(table: pd.DataFrame) -> dict:
    """Tablas del previsor ampliado de consumo y solar (battery.hard_solar.SolarCand). El ajuste está en
    scripts/p1_lab/hard_solar_cand.py (fit_prior), que es donde se diseñó."""
    lab = str(REPO / "scripts" / "p1_lab")
    if lab not in sys.path:
        sys.path.insert(0, lab)
    from hard_solar_cand import fit_prior
    return fit_prior(table)


def simulate_hard(agent, df: pd.DataFrame, known: int = KNOWN_HOURS, p=HARD_PARAMS):
    load_ = df["load_kw"].to_numpy(float); pv = df["pv_kw"].to_numpy(float)
    price = df["price_eur_kwh"].to_numpy(float); co2 = df["co2_kg_kwh"].to_numpy(float)
    met = {c: df[c].to_numpy(float) for c in METEO_COLS.values() if c in df}
    ts = pd.DatetimeIndex(df["timestamp"])
    n = len(df)
    soc = p.soc_init_kwh
    imp = np.zeros(n); exp = np.zeros(n); act = np.zeros(n); socs = np.zeros(n); infr = 0
    t_agent = 0.0
    for t in range(n):
        end = min(t + known, n)
        prev = t - 1 if t > 0 else t
        recent = {"ultim_consum_kw": float(load_[prev]), "ultima_solar_kw": float(pv[prev])}
        for c, v in met.items():
            recent[c] = float(v[prev])
        obs = {"timestamp": ts[t], "hour": int(ts[t].hour), "day_of_week": int(ts[t].dayofweek), "soc_kwh": float(soc),
               "soc_pct": float(soc / p.capacity_kwh), "soc_percent": float(soc / p.capacity_kwh * 100),
               "preu_actual": float(price[t]), "co2_actual": float(co2[t]),
               "preus_properes_24h": [float(v) for v in price[t:end]], "co2_properes_24h": [float(v) for v in co2[t:end]],
               "noves_dades_5min": recent, "cap_max_kwh": float(p.capacity_kwh), "power_max_kw": float(p.max_charge_kw)}
        t0 = time.perf_counter()
        a_req = float(agent.act(obs))
        t_agent += time.perf_counter() - t0
        a, soc, i = apply_action(soc, a_req, p)
        infr += i
        grid = load_[t] - pv[t] + a
        imp[t], exp[t], act[t], socs[t] = max(grid, 0.0), max(-grid, 0.0), a, soc
    totals = {"co2_kg": float((imp * co2).sum()), "cost_eur": float((imp * price).sum()), "infractions": infr,
              "export_kwh": float(exp.sum()), "runtime_s": t_agent, "final_soc_kwh": float(soc)}
    log = pd.DataFrame({"timestamp": ts, "load_kw": load_, "pv_kw": pv, "action_kw": act, "soc_kwh": socs, "import_kw": imp, "export_kw": exp})
    return totals, log


# ----------------------------------------------------------------------------------- agentes
class Nothing:
    def act(self, obs):
        return 0.0


class _Wrap:
    def __init__(self, policy):
        self.policy = policy

    def act(self, obs):
        return self.policy.act(obs)


def hard_agent(prior: dict, solar: dict = None, **cfg):
    """El agente del modo difícil con las tablas dadas (sin leer models/hard_*.json).
    cfg: yesterday_weight (mercado), z_discharge / z_charge (solar), y atributos de la política."""
    from battery.forecaster import FORECASTER_FILE, Forecaster
    from battery.hard_solar import make_netload
    from battery.policy import find_models_dir, load_json
    pol = HardPolicy()
    pol.market = MarketCand(prior, **{k: v for k, v in cfg.items() if k in ("yesterday_weight",)})
    pol.w_co2, pol.w_cost = score_weights(prior["co2_ref_kg_per_h"], prior["cost_ref_eur_per_h"])
    pol.forecaster = Forecaster(load_json(find_models_dir(), FORECASTER_FILE))
    pol.netload = make_netload(solar, pol.forecaster, **{k: v for k, v in cfg.items() if k in ("z_discharge", "z_charge")})
    for k, v in cfg.items():
        if k not in ("yesterday_weight", "z_discharge", "z_charge"):
            setattr(pol, k, v)
    return _Wrap(pol)


class _TrueMarket:
    """Previsor tramposo: devuelve el precio y el CO2 reales de las fechas pedidas (techo de la previsión)."""

    def __init__(self, df):
        self.price = dict(zip(df.timestamp, df.price_eur_kwh)); self.co2 = dict(zip(df.timestamp, df.co2_kg_kwh))
        self.fallback = MarketForecaster(None)

    def forecast(self, obs, times, weather=None):
        p = np.array([self.price.get(t, np.nan) for t in times]); c = np.array([self.co2.get(t, np.nan) for t in times])
        n = len(obs.price)
        p[:n], c[:n] = obs.price[:n], obs.co2[:n]
        for a in (p, c):
            bad = ~np.isfinite(a)
            if bad.any():
                a[bad] = a[~bad][-1] if (~bad).any() else 0.0
        return p, c


class _RowMarket:
    """Previsor tramposo por filas: las 24 filas siguientes del episodio, como en el modo estándar."""

    def __init__(self, df):
        self.price = df.price_eur_kwh.to_numpy(float); self.co2 = df.co2_kg_kwh.to_numpy(float); self.t = 0

    def forecast(self, obs, times, weather=None):
        t = self.t; self.t += 1
        p = self.price[t:t + len(times)]; c = self.co2[t:t + len(times)]
        if len(p) < len(times):
            p = np.r_[p, np.full(len(times) - len(p), p[-1])]; c = np.r_[c, np.full(len(times) - len(c), c[-1])]
        return p.copy(), c.copy()


def perfect_market_agent(prior: dict, df: pd.DataFrame, solar: dict = None):
    a = hard_agent(prior, solar)
    a.policy.market = _RowMarket(df)
    return a


def split_frame(full: pd.DataFrame, split: str) -> pd.DataFrame:
    """val: últimas 168 h de cada mes (RESERVADA para verificar). dev: días 8 a 14 de cada mes (para diseñar)."""
    if split == "val":
        return validation_split(full).reset_index(drop=True)
    if split == "dev":
        d = full[(full.timestamp.dt.day >= 8) & (full.timestamp.dt.day <= 14)]
        return d.reset_index(drop=True)
    if split == "train":
        return train_split(full).reset_index(drop=True)
    return full.reset_index(drop=True)


def load_factory(spec: str):
    """'ruta.py:func' -> la función `func` de ese fichero."""
    import importlib.util
    path, _, func = spec.partition(":")
    mod_spec = importlib.util.spec_from_file_location("cand_" + Path(path).stem, path)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    return getattr(mod, func)


def evaluate(split: str = "val", market: str = "", solar: str = "", only: str = "") -> pd.DataFrame:
    """Comparativa en `split`. Todo lo que se aprende (perfiles, modelos) se ajusta SIN las horas del split.

    market: 'ruta.py:func' con func(exclude: set de pd.Timestamp, prior: dict) -> objeto con
            .forecast(obs, times, weather) (contrato de battery.hard_market.MarketForecaster).
    solar:  'ruta.py:func' con func(exclude, base_forecaster) -> objeto con .update(obs, weather),
            .forecast(obs, times) y .adjust_action(action_kw, obs, p) (contrato de battery.hard_solar).
    """
    full = hard_table()
    df = split_frame(full, split)
    exclude = set(df.timestamp) if split in ("val", "dev") else None
    fit_df = full[~full.timestamp.isin(exclude)] if exclude else full
    prior = fit_market(exclude, fit_df)
    solar_prior = fit_solar(fit_df)
    base = baseline_totals(df)
    w = score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df))

    def candidate():
        a = hard_agent(prior, solar_prior)
        if market:
            a.policy.market = load_factory(market)(exclude or set(), prior)
        if solar:
            a.policy.netload = load_factory(solar)(exclude or set(), a.policy.forecaster)
        return a

    agents = {
        "nada": lambda: Nothing(),
        "plan de 3 h (sin prever)": lambda: hard_agent(prior, solar_prior, horizon=3),
        "mercado sin memoria (v4)": lambda: hard_agent({k: v for k, v in prior.items() if k != "cand"}, solar_prior),
        "solar sencilla (v6)": lambda: hard_agent(prior, {k: v for k, v in solar_prior.items() if k != "cand"}),
        "agente actual": lambda: hard_agent(prior, solar_prior),
        "precio y CO2 reales a 24 h": lambda: perfect_market_agent(prior, df, solar_prior),
        "óptimo (todo el futuro)": lambda: OracleAgent(df, *w, p=HARD_PARAMS),
    }
    if market or solar:
        agents["CANDIDATO"] = candidate
    if only:
        agents = {k: v for k, v in agents.items() if k in only.split(",")}
    rows = []
    for name, fac in agents.items():
        t0 = time.perf_counter()
        ag = fac()
        init_s = time.perf_counter() - t0
        totals, log = simulate_hard(ag, df)
        sc = score(totals, base)
        ex = log[log.export_kw > 1e-6]
        rows.append({"agente": name, "score": sc["score_raw"], "co2_pct": sc["d_co2_pct"], "coste_pct": sc["d_cost_pct"],
                     "infr": sc["infractions"], "vertido_kwh": totals["export_kwh"],
                     "vert_descarga": float(ex[ex.action_kw < -1e-6].export_kw.sum()),
                     "vert_solar": float(ex[ex.action_kw >= -1e-6].export_kw.sum()),
                     "ms_paso": 1000 * totals["runtime_s"] / len(df), "s_2016h": init_s + totals["runtime_s"] / len(df) * 2016})
    out = pd.DataFrame(rows)
    b_exp = float(np.maximum(df.pv_kw - df.load_kw, 0).sum())
    print(f"{split}: {len(df)} h | referencia {base['co2_kg']/len(df):.1f} kg/h y {base['cost_eur']/len(df):.1f} EUR/h | "
          f"excedente solar sin batería {b_exp:.0f} kWh ({100*(df.pv_kw>df.load_kw).mean():.1f} % de las horas)")
    print(out.round(3).to_string(index=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="val", choices=["val", "dev", "train", "todo"])
    ap.add_argument("--market", default="", help="candidato de previsión de precio y CO2: ruta.py:func")
    ap.add_argument("--solar", default="", help="candidato de previsión de consumo y solar: ruta.py:func")
    ap.add_argument("--only", default="", help="agentes a ejecutar, separados por comas")
    ap.add_argument("--out", default="", help="CSV donde guardar la tabla")
    ap.add_argument("--fit", action="store_true", help="guardar models/hard_market.json con todo el train")
    args = ap.parse_args()
    if args.fit:
        full = hard_table()
        prior = fit_market(None, full)
        (MODELS / "hard_market.json").write_text(json.dumps(prior), encoding="utf-8")
        (MODELS / "hard_solar.json").write_text(json.dumps(fit_solar(full)), encoding="utf-8")
        print("guardados models/hard_market.json y models/hard_solar.json")
        return 0
    out = evaluate(args.split, args.market, args.solar, args.only)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.out, index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
