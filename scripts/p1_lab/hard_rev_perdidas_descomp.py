"""Revisión "perdidas": dónde pierde puntos el agente del modo difícil frente al óptimo, hora a hora.

Owner: P1 (laboratorio). NO se empaqueta. Lee results/hourly/hard_<ventana>_*.csv (los guarda
`python scripts/p1_hard.py --split <ventana> --save-hourly`) y descompone la distancia al óptimo.

    python scripts/p1_lab/hard_rev_perdidas_descomp.py            # val, dev y 1-7
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
HOURLY = REPO / "results" / "hourly"
CAP, PMAX, ETA = 6000.0, 1500.0, 0.9 ** 0.5
AGENTS = {"v14": "agente_actual", "v10": "plan_con_margen_fijo__v10", "opt": "óptimo__todo_el_futuro"}


def load(win: str, slug: str) -> pd.DataFrame:
    d = pd.read_csv(HOURLY / f"hard_{win}_{slug}.csv", parse_dates=["timestamp"])
    base = np.maximum(d.load_kw - d.pv_kw, 0.0)
    n = len(d)
    co2_ref, cost_ref = (base * d.co2_kg_kwh).sum() / n, (base * d.price_eur_kwh).sum() / n
    d["w"] = 0.7 * d.co2_kg_kwh / co2_ref + 0.3 * d.price_eur_kwh / cost_ref
    d["wc"] = 0.7 * d.co2_kg_kwh / co2_ref
    d["wp"] = 0.3 * d.price_eur_kwh / cost_ref
    d["base"] = base
    d["pts"] = 100.0 * d.w * (base - d.import_kw) / n            # puntos de score que aporta cada hora
    d["pts_co2"] = 100.0 * d.wc * (base - d.import_kw) / n
    d["pts_eur"] = 100.0 * d.wp * (base - d.import_kw) / n
    d["hour"] = d.timestamp.dt.hour
    d["net"] = d.load_kw - d.pv_kw
    chg = np.maximum(d.action_kw, 0.0)
    dis = np.maximum(-d.action_kw, 0.0)
    d["grid_chg"] = np.minimum(chg, d.import_kw)                   # carga comprada a la red
    d["sun_chg"] = chg - d.grid_chg                                # carga con excedente solar
    d["waste_dis"] = np.where(dis > 1e-6, np.minimum(d.export_kw, dis), 0.0)   # descarga que se vierte
    d["use_dis"] = dis - d.waste_dis
    soc_prev = np.r_[CAP / 2, d.soc_kwh.to_numpy()[:-1]]
    d["soc_prev"] = soc_prev
    room = np.minimum(PMAX, (CAP - soc_prev) / ETA) - chg         # lo que aún cabía cargar esta hora
    d["lost_sun"] = np.where(dis <= 1e-6, np.minimum(d.export_kw, np.maximum(room, 0.0)), 0.0)
    d["full_sun"] = np.where(dis <= 1e-6, d.export_kw - d.lost_sun, 0.0)      # excedente con la batería llena
    return d


def resumen(win: str) -> None:
    D = {k: load(win, s) for k, s in AGENTS.items() if (HOURLY / f"hard_{win}_{s}.csv").exists()}
    if "opt" not in D:
        print(f"{win}: falta el óptimo"); return
    n = len(D["opt"])
    print(f"\n================ {win}: {n} h ================")
    rows = []
    for k, d in D.items():
        gc, ud = d.grid_chg.sum(), d.use_dis.sum()
        rows.append({"agente": k, "score": d.pts.sum(), "co2": d.pts_co2.sum(), "eur": d.pts_eur.sum(),
                     "compra_MWh": gc / 1e3, "w_compra": (d.grid_chg * d.w).sum() / max(gc, 1e-9),
                     "sol_MWh": d.sun_chg.sum() / 1e3, "desc_util_MWh": ud / 1e3,
                     "w_desc": (d.use_dis * d.w).sum() / max(ud, 1e-9),
                     "desc_tirada_kWh": d.waste_dis.sum(), "sol_perdido_kWh": d.lost_sun.sum(),
                     "sol_lleno_kWh": d.full_sun.sum(), "soc_final": d.soc_kwh.iloc[-1],
                     "ciclos": (d.use_dis.sum() + d.waste_dis.sum()) / ETA / CAP})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    opt = D["opt"]
    for k in ("v14", "v10"):
        if k not in D:
            continue
        d = D[k]
        gap = opt.pts.sum() - d.pts.sum()
        # valor de la energía según el propio agente: peso medio al que descarga
        wdis = (d.use_dis * d.w).sum() / max(d.use_dis.sum(), 1e-9)
        f = 100.0 / n
        tirada = f * wdis * d.waste_dis.sum()                     # si esa descarga se hubiera aprovechado a su peso medio
        sol = f * wdis * ETA * ETA * d.lost_sun.sum()             # excedente no guardado, devuelto con pérdidas
        final = f * wdis * ETA * d.soc_kwh.iloc[-1]               # carga que sobra al final del episodio
        print(f"\n[{k}] distancia al óptimo: {gap:.3f} puntos (CO2 {opt.pts_co2.sum()-d.pts_co2.sum():+.3f}, "
              f"coste {opt.pts_eur.sum()-d.pts_eur.sum():+.3f})")
        print(f"   descarga tirada  {d.waste_dis.sum():8.0f} kWh  ~ {tirada:.3f} pt")
        print(f"   solar no guardada {d.lost_sun.sum():7.0f} kWh  ~ {sol:.3f} pt  (con batería llena, inevitable a corto: {d.full_sun.sum():.0f} kWh; el óptimo {opt.full_sun.sum():.0f})")
        print(f"   carga al final    {d.soc_kwh.iloc[-1]:7.0f} kWh  ~ {final:.3f} pt  (el óptimo acaba con {opt.soc_kwh.iloc[-1]:.0f})")
        dthr = (d.grid_chg.sum() - opt.grid_chg.sum()) / 1e3
        print(f"   compra a la red: {d.grid_chg.sum()/1e3:.1f} MWh a peso {(d.grid_chg*d.w).sum()/d.grid_chg.sum():.4f}; "
              f"óptimo {opt.grid_chg.sum()/1e3:.1f} MWh a {(opt.grid_chg*opt.w).sum()/opt.grid_chg.sum():.4f} ({dthr:+.1f} MWh)")
        print(f"   descarga útil:   {d.use_dis.sum()/1e3:.1f} MWh a peso {wdis:.4f}; "
              f"óptimo {opt.use_dis.sum()/1e3:.1f} MWh a {(opt.use_dis*opt.w).sum()/opt.use_dis.sum():.4f}")
        t = pd.DataFrame({"hora": range(24)}).set_index("hora")
        g = d.groupby("hour"); go = opt.groupby("hour")
        t["d_pts"] = (g.pts.sum() - go.pts.sum())
        t["d_co2"] = (g.pts_co2.sum() - go.pts_co2.sum())
        t["d_eur"] = (g.pts_eur.sum() - go.pts_eur.sum())
        t["act"] = g.action_kw.mean(); t["act_opt"] = go.action_kw.mean()
        t["compra"] = g.grid_chg.mean(); t["compra_opt"] = go.grid_chg.mean()
        t["desc"] = g.use_dis.mean(); t["desc_opt"] = go.use_dis.mean()
        t["tirada"] = g.waste_dis.mean(); t["sol_perd"] = g.lost_sun.mean()
        t["soc"] = g.soc_kwh.mean(); t["soc_opt"] = go.soc_kwh.mean()
        t["w"] = g.w.mean()
        t["lleno%"] = 100 * g.soc_kwh.apply(lambda s: (s > CAP - 1).mean()); t["lleno_opt%"] = 100 * go.soc_kwh.apply(lambda s: (s > CAP - 1).mean())
        t["vacio%"] = 100 * g.soc_kwh.apply(lambda s: (s < 1).mean()); t["vacio_opt%"] = 100 * go.soc_kwh.apply(lambda s: (s < 1).mean())
        print(t.round(3).to_string())
        out = REPO / "results" / "p1_hard" / f"rev_perdidas_{win}_{k}_por_hora.csv"
        t.round(4).to_csv(out)


if __name__ == "__main__":
    wins = sys.argv[1:] or ["val", "dev", "1-7"]
    pd.set_option("display.width", 250)
    for w in wins:
        resumen(w)
