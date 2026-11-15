"""Cierre: el agent.py del ZIP de la v15 (P2) frente al del ZIP FINAL (HARD_v14_SUBIR_ESTE.zip), en la ventana val.

Mundo A (documentado): la meteo de la observación es de la hora anterior (como scripts/p1_hard.py simulate_hard).
Mundo B (alternativo): la meteo de la observación es de la hora actual (consumo y solar siguen siendo de la anterior).

Uso: python scripts/p1_lab/hard_cierre_v15zip_compara.py <carpeta_final> <carpeta_v15> [A|B|AB]
"""
import copy
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard as H  # noqa: E402
from battery.sim import apply_action, baseline_totals, score  # noqa: E402

P = H.HARD_PARAMS


def load_agent(folder: str, name: str):
    spec = importlib.util.spec_from_file_location(name, str(Path(folder) / "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.BatteryAgent()


def find_attr(obj, name, depth=4, seen=None):
    seen = seen if seen is not None else set()
    if id(obj) in seen or depth < 0:
        return None
    seen.add(id(obj))
    d = getattr(obj, "__dict__", None)
    if not isinstance(d, dict):
        return None
    if name in d:
        return obj
    for v in d.values():
        r = find_attr(v, name, depth - 1, seen)
        if r is not None:
            return r
    return None


def make_obs(df_arr, t, soc, now_meteo: bool, mutate=None):
    load_, pv, price, co2, met, ts, n = df_arr
    end = min(t + H.KNOWN_HOURS, n)
    prev = t - 1 if t > 0 else t
    recent = {"ultim_consum_kw": float(load_[prev]), "ultima_solar_kw": float(pv[prev])}
    for c, v in met.items():
        recent[c] = float(v[t if now_meteo else prev])
    obs = {"timestamp": ts[t], "hour": int(ts[t].hour), "day_of_week": int(ts[t].dayofweek), "soc_kwh": float(soc),
           "soc_pct": float(soc / P.capacity_kwh), "soc_percent": float(soc / P.capacity_kwh * 100),
           "preu_actual": float(price[t]), "co2_actual": float(co2[t]),
           "preus_properes_24h": [float(v) for v in price[t:end]], "co2_properes_24h": [float(v) for v in co2[t:end]],
           "noves_dades_5min": recent, "cap_max_kwh": float(P.capacity_kwh), "power_max_kw": float(P.max_charge_kw)}
    if mutate is not None:
        mutate(obs, t)
    return obs


def arrays(df):
    import pandas as pd
    met = {c: df[c].to_numpy(float) for c in H.METEO_COLS.values() if c in df}
    return (df["load_kw"].to_numpy(float), df["pv_kw"].to_numpy(float), df["price_eur_kwh"].to_numpy(float),
            df["co2_kg_kwh"].to_numpy(float), met, pd.DatetimeIndex(df["timestamp"]), len(df))


def run(agent, df, now_meteo: bool, shadow=None, mutate=None, label=""):
    """Simula con `agent`. Si hay `shadow`, recibe copias de las mismas observaciones y se mide la diferencia."""
    A = arrays(df)
    load_, pv, price, co2, met, ts, n = A
    soc = P.soc_init_kwh
    imp = np.zeros(n); infr = 0; infr_sh = 0; tt = []; tt_sh = []
    dmax = 0.0; ndiff = 0; first = None; exc = 0
    holder = find_attr(agent, "irr_now")
    holder_sh = find_attr(shadow, "irr_now") if shadow is not None else None
    on = 0; on_sh = 0; first_on = None
    for t in range(n):
        obs = make_obs(A, t, soc, now_meteo, mutate)
        t0 = time.perf_counter()
        try:
            a_req = float(agent.act(copy.deepcopy(obs)))
        except Exception:
            exc += 1; a_req = 0.0
        tt.append(time.perf_counter() - t0)
        if holder is not None and holder.irr_now:
            on += 1
            first_on = first_on if first_on is not None else str(ts[t])
        if shadow is not None:
            t0 = time.perf_counter()
            try:
                b_req = float(shadow.act(copy.deepcopy(obs)))
            except Exception:
                exc += 1; b_req = 0.0
            tt_sh.append(time.perf_counter() - t0)
            d = abs(a_req - b_req)
            if d > 0:
                ndiff += 1
                first = first if first is not None else (str(ts[t]), a_req, b_req)
            dmax = max(dmax, d)
            infr_sh += apply_action(soc, b_req, P)[2]
            if holder_sh is not None and holder_sh.irr_now:
                on_sh += 1
                first_on = first_on if first_on is not None else str(ts[t])
        a, soc, i = apply_action(soc, a_req, P)
        infr += i
        imp[t] = max(load_[t] - pv[t] + a, 0.0)
    totals = {"co2_kg": float((imp * co2).sum()), "cost_eur": float((imp * price).sum()), "infractions": infr,
              "runtime_s": float(sum(tt)), "final_soc_kwh": float(soc)}
    s = score(totals, baseline_totals(df))
    out = {"label": label, "score": round(float(s["score"]), 4), "d_co2": round(float(s["d_co2_pct"]), 4),
           "d_cost": round(float(s["d_cost_pct"]), 4), "infr": infr, "exc": exc,
           "ms_medio": round(1000 * float(np.mean(tt)), 2), "ms_max": round(1000 * float(np.max(tt)), 1),
           "t_total_s": round(float(sum(tt)), 1), "horas_irr_now": on, "primera_irr_now": first_on}
    if shadow is not None:
        used = getattr(holder_sh, "irr_used", None) if holder_sh is not None else None
        out.update({"sombra_dif_max_kw": dmax, "sombra_horas_distintas": ndiff, "sombra_primera": first,
                    "sombra_infr": infr_sh, "sombra_ms_medio": round(1000 * float(np.mean(tt_sh)), 2),
                    "sombra_ms_max": round(1000 * float(np.max(tt_sh)), 1), "sombra_horas_irr_now": on_sh,
                    "sombra_irr_used": used})
    else:
        out["irr_used"] = getattr(holder, "irr_used", None) if holder is not None else None
    print(out, flush=True)
    return out


def main():
    d_final, d_v15 = sys.argv[1], sys.argv[2]
    what = sys.argv[3] if len(sys.argv) > 3 else "AB"
    full = H.hard_table()
    df = H.split_frame(full, "val")
    print("val:", len(df), "horas", df.timestamp.min(), df.timestamp.max(), flush=True)
    if "A" in what:
        print("== MUNDO A (meteo de la hora anterior): FINAL conduce, v15 en sombra con las mismas observaciones", flush=True)
        run(load_agent(d_final, "ag_final_a"), df, False, shadow=load_agent(d_v15, "ag_v15_a"), label="A final+sombra v15")
    if "B" in what:
        print("== MUNDO B (meteo de la hora actual): cada uno con su trayectoria", flush=True)
        run(load_agent(d_final, "ag_final_b"), df, True, label="B final")
        run(load_agent(d_v15, "ag_v15_b"), df, True, label="B v15")
    if "C" in what:
        # Deformaciones en el mundo A: la v15 conduce y la FINAL va en sombra (¿se dispara el detector?)
        rng = np.random.default_rng(7)
        nan_mask = rng.random(len(df)) < 0.3

        def irr_nan(obs, t):
            if nan_mask[t]:
                obs["noves_dades_5min"]["irradiancia_wm2"] = float("nan")

        def irr_falta(obs, t):
            if nan_mask[t]:
                obs["noves_dades_5min"].pop("irradiancia_wm2", None)

        def sin_meteo(obs, t):
            for k in list(obs["noves_dades_5min"]):
                if k not in ("ultim_consum_kw", "ultima_solar_kw"):
                    obs["noves_dades_5min"].pop(k)

        def contador_cero_sem(obs, t):
            if (t // 168) in (2, 7):
                obs["noves_dades_5min"]["ultim_consum_kw"] = 0.0
                obs["noves_dades_5min"]["ultima_solar_kw"] = 0.0

        def solar_nan(obs, t):
            if nan_mask[t]:
                obs["noves_dades_5min"]["ultima_solar_kw"] = float("nan")

        for nm, fn in (("irr NaN 30%", irr_nan), ("irr ausente 30%", irr_falta), ("sin meteo", sin_meteo),
                       ("contador 0 en 2 semanas", contador_cero_sem), ("solar NaN 30%", solar_nan)):
            print("== MUNDO A deformado:", nm, flush=True)
            run(load_agent(d_v15, "ag_v15_c"), df, False, shadow=load_agent(d_final, "ag_final_c"), mutate=fn,
                label="A-def v15+sombra final: " + nm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
