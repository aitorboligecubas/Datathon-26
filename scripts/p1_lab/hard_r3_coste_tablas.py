"""Tablas del encargo "coste" (ronda 3) a partir de results/hourly/r3_coste_<ventana>.pkl.

    python scripts/p1_lab/hard_r3_coste_tablas.py            # dev, 1-7 y val (las que existan)
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "p1_hard"
PKL = OUT.parent / "hourly"      # los .pkl pesan 5 MB cada uno: van a results/hourly/, que git ignora
PKL.mkdir(parents=True, exist_ok=True)
wins = [w for w in (sys.argv[1:] or ["dev", "1-7", "val"]) if (PKL / f"r3_coste_{w}.pkl").exists()]
data = {w: pickle.load(open(PKL / f"r3_coste_{w}.pkl", "rb")) for w in wins}


def masks_for(n):
    hw = np.arange(n) % 168
    hour = hw % 24
    return {"todo": np.ones(n, bool), "horas pares": hour % 2 == 0, "bloques 3 h pares": (hw // 3) % 2 == 0,
            "bloques 6 h impares": (hw // 6) % 2 == 1}


def pct(d, name, mask):
    o = d["out"][name]
    co2 = 100 * o["co2"][mask].sum() / d["base_co2"][mask].sum()
    eur = 100 * o["eur"][mask].sum() / d["base_eur"][mask].sum()
    return 0.7 * co2 + 0.3 * eur, co2, eur


names = []
for w in wins:
    for n in data[w]["out"]:
        if n not in names:
            names.append(n)
MASKS = list(masks_for(168).keys())

print("## 1. Episodio completo: score, CO2 % y coste % (y diferencia frente a su base, v10 o v14)\n")
for w in wins:
    d = data[w]
    all_ = masks_for(len(d["base_co2"]))["todo"]
    print(f"### Ventana {w}\n")
    print("| variante | score | CO2 % | coste % | d score | d CO2 | d coste | vertido kWh |")
    print("|---|---|---|---|---|---|---|---|")
    for n in names:
        if n not in d["out"]:
            continue
        b = n[:3]
        s, c, e = pct(d, n, all_)
        sb, cb, eb = pct(d, b, all_)
        print(f"| {n} | {s:.3f} | {c:.3f} | {e:.3f} | {s - sb:+.3f} | {c - cb:+.3f} | {e - eb:+.3f} | {d['out'][n]['export']:.0f} |")
    print()

print("## 2. Media de las ventanas: diferencia frente a su base (score / CO2 / coste), episodio completo y máscaras\n")
print(f"Ventanas: {wins}\n")
print("| variante | " + " | ".join(MASKS) + " |")
print("|---|" + "---|" * len(MASKS))
for n in names:
    if n in ("v10", "v14"):
        continue
    cells = []
    for m in MASKS:
        ds = []
        for w in wins:
            d = data[w]
            if n not in d["out"]:
                continue
            mask = masks_for(len(d["base_co2"]))[m]
            ds.append(np.array(pct(d, n, mask)) - np.array(pct(d, n[:3], mask)))
        if ds:
            v = np.mean(ds, axis=0)
            cells.append(f"{v[0]:+.3f} / {v[1]:+.3f} / {v[2]:+.3f} ({len(ds)})")
        else:
            cells.append("")
    print(f"| {n} | " + " | ".join(cells) + " |")
print()


print("## 2 bis. Público frente a privado, ventana a ventana: d score (d CO2 / d coste) frente a su base en la máscara y en su complemento\n")
KEY = ["v10 coste x1.5", "v14 coste x1.5", "v10 coste x2", "v14 coste x2", "v14 coste x0.75", "v10 margen 0.8", "v14 incert. x0.7", "v14 incert. x0.5",
       "v10 margen 1.2", "v14 incert. x1.3", "v14 precio real", "v14 CO2 real"]
for m in MASKS[1:]:
    print(f"### Máscara: {m}\n")
    print("| variante | " + " | ".join(f"{w}: pública | {w}: privada" for w in wins) + " |")
    print("|---|" + "---|---|" * len(wins))
    for n in KEY:
        cells = []
        for w in wins:
            d = data[w]
            if n not in d["out"]:
                cells += ["", ""]
                continue
            mask = masks_for(len(d["base_co2"]))[m]
            for mk_ in (mask, ~mask):
                v = np.array(pct(d, n, mk_)) - np.array(pct(d, n[:3], mk_))
                cells.append(f"{v[0]:+.2f} ({v[1]:+.2f} / {v[2]:+.2f})")
        print(f"| {n} | " + " | ".join(cells) + " |")
    print()

print("## 2 ter. Máscaras al azar (la mitad de las horas de cada semana, 1.000 por ventana): ¿cómo se ve cada cambio en la mitad pública?\n")
print("Firma de los líderes: coste >= +0,7 puntos con el CO2 dentro de +-0,15.\n")
print("| variante | d score completo | d CO2 pública: media (p5 a p95) | d coste pública: media (p5 a p95) | d score pública: media (p5 a p95) | % máscaras con la firma | % con d score pública > 0 |")
print("|---|---|---|---|---|---|---|")
rng = np.random.default_rng(0)
RM = {}
for w in wins:
    n = len(data[w]["base_co2"])
    ms = np.zeros((1000, n), bool)
    for i in range(1000):
        for s0 in range(0, n, 168):
            idx = np.arange(s0, min(s0 + 168, n))
            ms[i, rng.choice(idx, len(idx) // 2, replace=False)] = True
    RM[w] = ms.astype(float)
for nme in [x for x in names if x not in ("v10", "v14")]:
    dc, de, full_ = [], [], []
    for w in wins:
        d = data[w]
        if nme not in d["out"]:
            continue
        M = RM[w]
        b = nme[:3]
        bc, be = M @ d["base_co2"], M @ d["base_eur"]
        dc.append(100 * (M @ (d["out"][nme]["co2"] - d["out"][b]["co2"])) / bc)
        de.append(100 * (M @ (d["out"][nme]["eur"] - d["out"][b]["eur"])) / be)
        al = np.ones(len(d["base_co2"]), bool)
        full_.append(pct(d, nme, al)[0] - pct(d, b, al)[0])
    if not dc:
        continue
    dc, de = np.concatenate(dc), np.concatenate(de)
    ds = 0.7 * dc + 0.3 * de
    q = lambda x: f"{x.mean():+.2f} ({np.percentile(x, 5):+.2f} a {np.percentile(x, 95):+.2f})"
    firma = 100 * np.mean((de >= 0.7) & (np.abs(dc) <= 0.15))
    print(f"| {nme} | {np.mean(full_):+.3f} | {q(dc)} | {q(de)} | {q(ds)} | {firma:.0f} | {100 * np.mean(ds > 0):.0f} |")
print()

print("## 3. Error de la previsión de precio y CO2 (antelaciones 3-23 h), agente actual (v14)\n")
recs = [data[w]["rec"]["v14"].assign(win=w) for w in wins if "v14" in data[w].get("rec", {})]
if recs:
    r = pd.concat(recs, ignore_index=True)
    r["target"] = pd.to_datetime(r["target"])
    r["ep"] = (r.p_fc - r.p); r["ec"] = (r.c_fc - r.c)
    r["hour"] = r.target.dt.hour; r["month"] = r.target.dt.month
    r["tipo"] = np.where(r.target.dt.dayofweek < 5, "laborable", np.where(r.target.dt.dayofweek == 5, "sábado", "domingo"))
    r["lead"] = pd.cut(r.k, [2, 5, 11, 17, 23], labels=["3-5", "6-11", "12-17", "18-23"])
    r["franja"] = pd.cut(r.hour, [-1, 7, 9, 13, 17, 21, 23], labels=["0-7 valle", "8-9 llano", "10-13 punta", "14-17 llano", "18-21 punta", "22-23 llano"])

    def tab(key):
        g = r.groupby(key, observed=True)
        t = pd.DataFrame({"n": g.size(), "precio medio": g.p.mean(), "MAE precio": g.ep.apply(lambda x: x.abs().mean()),
                          "sesgo precio": g.ep.mean(), "CO2 medio": g.c.mean(), "MAE CO2": g.ec.apply(lambda x: x.abs().mean()),
                          "sesgo CO2": g.ec.mean()})
        t["MAE precio %"] = 100 * t["MAE precio"] / t["precio medio"]
        t["MAE CO2 %"] = 100 * t["MAE CO2"] / t["CO2 medio"]
        t["sesgo precio %"] = 100 * t["sesgo precio"] / t["precio medio"]
        return t[["n", "precio medio", "MAE precio %", "sesgo precio %", "CO2 medio", "MAE CO2 %"]].round(4)

    for key in ("lead", "franja", "tipo", "month", "win"):
        print(f"Por {key}:\n")
        print('```'); print(tab(key).to_string()); print('```')
        print()
    # variación dentro del día: lo que importa para mover energía es el ORDEN de las horas, no el nivel
    q = r[r.k >= 3].copy()
    g = q.groupby(["win", "now"])
    cp = g.apply(lambda x: np.corrcoef(x.p_fc, x.p)[0, 1] if x.p.std() > 0 and x.p_fc.std() > 0 else np.nan)
    cc = g.apply(lambda x: np.corrcoef(x.c_fc, x.c)[0, 1] if x.c.std() > 0 and x.c_fc.std() > 0 else np.nan)
    sp = g.apply(lambda x: x.p.std() / x.p.mean())
    sc = g.apply(lambda x: x.c.std() / x.c.mean())
    print(f"Correlación previsto-real dentro de cada horizonte (3-23 h): precio {cp.mean():.3f} (mediana {cp.median():.3f}), "
          f"CO2 {cc.mean():.3f} (mediana {cc.median():.3f})")
    print(f"Variación relativa dentro del horizonte (desv. típica / media): precio {sp.mean():.3f}, CO2 {sc.mean():.3f}")
