"""Verificación independiente del candidato 'solar' (HARD MODE): fugas de datos y error de previsión en val.

    python results/p1_hard/solar_verif_fugas.py

1. Fuga al ajustar: se estropean (valores al azar) las horas de `exclude` en la tabla y se vuelve a ajustar.
   Si las tablas salen idénticas, el ajuste no mira esas horas. Control: estropear 50 horas de fuera sí
   tiene que cambiarlas.
2. Caché de `to_prior`: ¿devuelve tablas viejas con otro `exclude` del mismo tamaño y mismo mínimo?
3. Tablas de models/hard_solar.json ("cand") frente a `to_prior(None)`: ¿son las del candidato?
4. Causalidad al prever: dos series iguales hasta la hora t y distintas después dan la misma previsión en t.
5. Error de previsión FUERA de muestra en val (tablas ajustadas sin val), agente de partida y candidato.
No se empaqueta. No toca nada del repo.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard as bench  # noqa: E402
from battery.forecaster import FORECASTER_FILE, Forecaster  # noqa: E402
from battery.hard_solar import NetLoadForecaster  # noqa: E402
from battery.obs import Obs  # noqa: E402
from battery.policy import find_models_dir, load_json  # noqa: E402

make = bench.load_factory(str(REPO / "scripts" / "p1_lab" / "hard_solar_cand.py") + ":make")
G = make.__globals__
to_prior, PRIOR_CACHE, SolarCand = G["to_prior"], G["PRIOR_CACHE"], G["SolarCand"]
REAL_TABLE = bench.hard_table()
VALUE_COLS = [c for c in REAL_TABLE.columns if c != "timestamp"]


def dumps(prior) -> str:
    return json.dumps(prior, sort_keys=True)


def corrupted(mask: np.ndarray, seed: int) -> pd.DataFrame:
    """La tabla con valores al azar (y muy distintos) en las filas de `mask`."""
    t = REAL_TABLE.copy()
    rng = np.random.default_rng(seed)
    for c in VALUE_COLS:
        t.loc[mask, c] = rng.uniform(0.0, 5.0, int(mask.sum())) * float(np.nanmax(np.abs(REAL_TABLE[c])) + 1.0)
    return t


def prior_with(table: pd.DataFrame, exclude) -> str:
    PRIOR_CACHE.clear()
    bench.hard_table = lambda: table.copy()
    try:
        return dumps(to_prior(exclude))
    finally:
        bench.hard_table = lambda: REAL_TABLE.copy()
        PRIOR_CACHE.clear()


def leak_at_fit() -> None:
    print("1. FUGA AL AJUSTAR")
    for split in ("dev", "val"):
        df = bench.split_frame(REAL_TABLE, split)
        exclude = set(df.timestamp)
        inside = REAL_TABLE.timestamp.isin(exclude).to_numpy()
        ref = prior_with(REAL_TABLE, exclude)
        same = [prior_with(corrupted(inside, s), exclude) == ref for s in (1, 2, 3)]
        rng = np.random.default_rng(7)
        out_rows = np.zeros(len(REAL_TABLE), bool)
        out_rows[rng.choice(np.flatnonzero(~inside), 50, replace=False)] = True
        control = prior_with(corrupted(out_rows, 4), exclude) != ref
        full = prior_with(REAL_TABLE, None)
        print(f"   {split}: {int(inside.sum())} horas excluidas | tablas idénticas con esas horas estropeadas (3 semillas): {same} | "
              f"control (estropear 50 horas de fuera cambia las tablas): {control} | distintas de las de todo el train: {full != ref}")


def cache_defect() -> None:
    print("2. CACHÉ DE to_prior")
    df = bench.split_frame(REAL_TABLE, "dev")
    ex1 = set(df.timestamp)
    ordered = sorted(ex1)
    other = REAL_TABLE.timestamp[~REAL_TABLE.timestamp.isin(ex1)].iloc[-200:]      # 200 horas de fuera, al final
    ex2 = set(ordered[:-200]) | set(other)                                          # mismo tamaño y mismo mínimo
    PRIOR_CACHE.clear()
    a = to_prior(ex1)
    b = to_prior(ex2)
    PRIOR_CACHE.clear()
    b_fresh = to_prior(ex2)
    print(f"   exclude distinto (200 horas cambiadas), mismo tamaño y mismo mínimo: devuelve el MISMO objeto = {a is b} | "
          f"las tablas buenas serían distintas = {dumps(b_fresh) != dumps(a)}")
    PRIOR_CACHE.clear()


def models_json() -> None:
    print("3. models/hard_solar.json")
    try:
        stored = json.loads((REPO / "models" / "hard_solar.json").read_text(encoding="utf-8")).get("cand")
    except Exception as exc:
        print("   no se puede leer:", exc); return
    if not stored:
        print("   no tiene la clave 'cand'"); return
    PRIOR_CACHE.clear()
    full = to_prior(None)
    diff = [k for k in sorted(set(stored) | set(full)) if k != "net_sd" and json.dumps(stored.get(k)) != json.dumps(full.get(k))]
    print(f"   claves de 'cand': {len(stored)} | distintas de to_prior(None): {diff or 'ninguna'}")


def make_obs(ts, load_prev, pv_prev) -> Obs:
    return Obs(hour=int(ts.hour), weekday=int(ts.dayofweek), soc_kwh=3000.0, price=np.array([0.1, 0.1, 0.1]),
               co2=np.array([0.1, 0.1, 0.1]), load_prev_kw=float(load_prev), pv_prev_kw=float(pv_prev), timestamp=ts)


def new_base() -> Forecaster:
    return Forecaster(load_json(find_models_dir(), FORECASTER_FILE))


def walk(f, df: pd.DataFrame, horizon: int = 24, corrupt_from: int = -1):
    """Pasa el previsor por el episodio como lo hace HardPolicy (primera hora de cada bloque sin lectura).
    Devuelve las previsiones de consumo y solar [paso, antelación]."""
    ts = pd.DatetimeIndex(df.timestamp)
    load = df.load_kw.to_numpy(float).copy(); pv = df.pv_kw.to_numpy(float).copy()
    if corrupt_from >= 0:
        load[corrupt_from:] = 7777.0; pv[corrupt_from:] = 3333.0
    n = len(df)
    L, P = np.full((n, horizon), np.nan), np.full((n, horizon), np.nan)
    for t in range(n):
        first = t == 0 or (ts[t] - ts[t - 1]) != pd.Timedelta(hours=1)
        if first:
            f.new_block()
            obs = make_obs(ts[t], float("nan"), float("nan"))
        else:
            obs = make_obs(ts[t], load[t - 1], pv[t - 1])
        f.update(obs, {})
        times = [ts[t] + pd.Timedelta(hours=k) for k in range(horizon)]
        lo, p_ = f.forecast(obs, times)
        L[t], P[t] = lo, p_
    return L, P


def causality() -> None:
    print("4. CAUSALIDAD AL PREVER")
    df = bench.split_frame(REAL_TABLE, "val")
    exclude = set(df.timestamp)
    PRIOR_CACHE.clear()
    prior = to_prior(exclude)
    L0, P0 = walk(SolarCand(prior, new_base()), df)
    ok, changed = True, 0
    for cut in (300, 777, 1200):
        L1, P1 = walk(SolarCand(prior, new_base()), df, corrupt_from=cut)
        # en el paso `cut` la lectura que llega es la de cut-1 (intacta): hasta ahí todo tiene que ser idéntico
        ok = ok and np.array_equal(L0[:cut + 1], L1[:cut + 1]) and np.array_equal(P0[:cut + 1], P1[:cut + 1])
        changed += int(not np.array_equal(L0[cut + 1:cut + 3], L1[cut + 1:cut + 3]))
    print(f"   previsiones idénticas hasta la hora del corte (3 cortes): {ok} | cambian justo después (control): {changed} de 3")


def errors_out_of_sample() -> None:
    print("5. ERROR DE PREVISIÓN FUERA DE MUESTRA (tablas sin las horas del split)")
    for split in ("dev", "val"):
        df = bench.split_frame(REAL_TABLE, split)
        exclude = set(df.timestamp)
        fit_df = REAL_TABLE[~REAL_TABLE.timestamp.isin(exclude)]
        simple = {k: v for k, v in bench.fit_solar(fit_df).items() if k != "cand"}
        PRIOR_CACHE.clear()
        prior = to_prior(exclude)
        ts = pd.DatetimeIndex(df.timestamp)
        load = df.load_kw.to_numpy(float); pv = df.pv_kw.to_numpy(float)
        n = len(df)
        fa = NetLoadForecaster(simple, new_base())
        base_b = new_base()
        base_b.pv_prior = base_b.pv_prior * 12.0
        fb = SolarCand(prior, base_b, z=0.0)             # z = 0: la solar que devuelve es la previsión, sin margen
        La, Pa = walk(fa, df)
        Lb, Pb = walk(fb, df)
        sd = np.asarray(simple["net_sd"], float)
        rows = []
        for k in (0, 1, 3, 6, 12):
            idx = np.arange(n - k)
            same = (ts[idx + k] - ts[idx]) == pd.Timedelta(hours=k)          # la hora prevista está en el mismo bloque
            warm = np.array([t > 0 and (ts[t] - ts[t - 1]) == pd.Timedelta(hours=1) for t in idx])
            m = same & warm & (load[idx + k] > 0)
            ya, yp = load[idx + k][m], pv[idx + k][m]
            pa = Pa[idx, k][m] - (sd[ts[idx + k].hour][m] if k >= 1 else 0.0)  # el previsor sencillo suma 1 desv. típica a partir de k = 1
            day = yp > 30.0
            rows.append({"antelación_h": k, "n": int(m.sum()),
                         "consumo_partida": float(np.sqrt(np.mean((La[idx, k][m] - ya) ** 2))),
                         "consumo_cand": float(np.sqrt(np.mean((Lb[idx, k][m] - ya) ** 2))),
                         "solar_día_partida": float(np.sqrt(np.mean((pa[day] - yp[day]) ** 2))),
                         "solar_día_cand": float(np.sqrt(np.mean((Pb[idx, k][m][day] - yp[day]) ** 2)))})
        print(f"   {split} (raíz del error cuadrático medio, kW; 'solar_día' = horas con más de 30 kW de solar):")
        print("   " + pd.DataFrame(rows).round(1).to_string(index=False).replace("\n", "\n   "))
        # cobertura de los márgenes en la hora actual: ¿cada cuánto el consumo neto real queda por debajo del tope de descarga?
        fc = SolarCand(prior, new_base_x12())
        ts_ok, below, n_ok = [], 0, 0
        for t in range(n):
            first = t == 0 or (ts[t] - ts[t - 1]) != pd.Timedelta(hours=1)
            if first:
                fc.new_block(); obs = make_obs(ts[t], float("nan"), float("nan"))
            else:
                obs = make_obs(ts[t], load[t - 1], pv[t - 1])
            fc.update(obs, {})
            fc.forecast(obs, [ts[t]])
            if not first and load[t] > 0 and fc.net_lo0 > 0:
                n_ok += 1
                below += int(load[t] - pv[t] < fc.net_lo0)
        print(f"   {split}: el consumo neto real queda por debajo del tope de descarga (previsto - margen) en {below} de {n_ok} horas "
              f"con tope positivo ({100 * below / max(n_ok, 1):.1f} %; con cuantiles 16 % y 84 % bien calibrados, cerca del 16 %)")


def new_base_x12() -> Forecaster:
    b = new_base()
    b.pv_prior = b.pv_prior * 12.0
    return b


if __name__ == "__main__":
    leak_at_fit()
    cache_defect()
    models_json()
    causality()
    errors_out_of_sample()
