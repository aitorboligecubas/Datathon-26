"""Revisión de REGLAS Y ENTORNO: ¿puede explicarse un +16 % en el público sin conocer la máscara?

Owner: P1. NO se empaqueta. No simula nada: usa los registros hora a hora que ya existen
(results/hourly/calcal_<ventana>.pkl y hard_<ventana>_óptimo__todo_el_futuro.csv).

    python scripts/p1_lab/hard_fin_reglas_mascara.py [val|dev|1-7]

1. Para muchas familias de máscara "50 % de cada semana" (mitades, bloques alternos, horas al azar...), la nota
   pública del óptimo que conoce todo el futuro frente a la de la v10. Si ninguna llega a x1,16 (27,98 / 24,15),
   prever mejor no explica esa entrega con ninguna máscara.
2. El techo de un agente que SÍ conociera la máscara (LP que solo paga las horas públicas): cuánto sube el público
   y cuánto se hunde el privado. No es una propuesta: es la medida de la asimetría de evaluate_results(mask=...).
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.optimize import linprog

REPO = Path(__file__).resolve().parents[2]
CAP, POW, ETA = 6000.0, 1500.0, 0.9 ** 0.5
OBJ = {"score": 27.98 / 24.15, "co2": 27.05 / 22.92, "eur": 30.15 / 27.02}


def score(sav_co2, sav_eur, b_co2, b_eur, m):
    c = 100.0 * sav_co2[m].sum() / b_co2[m].sum()
    e = 100.0 * sav_eur[m].sum() / b_eur[m].sum()
    return 0.7 * c + 0.3 * e, c, e


def masks(n_weeks, rng):
    """(familia, máscara de 168·n_weeks horas con la mitad de cada semana)."""
    h = np.arange(168)
    for b in (1, 2, 3, 4, 6, 12, 42, 84):                      # bloques alternos de b horas, las dos fases
        base = (h // b) % 2 == 0
        if base.sum() == 84:
            yield f"bloques de {b} h (fase A)", np.tile(base, n_weeks)
            yield f"bloques de {b} h (fase B)", np.tile(~base, n_weeks)
    for k in range(0, 168, 6):                                 # 84 h seguidas empezando en la hora k (circular)
        yield "84 h seguidas, inicio variable", np.tile(((h - k) % 168) < 84, n_weeks)
    for _ in range(1500):                                      # 84 horas al azar, el mismo patrón todas las semanas
        base = np.zeros(168, bool)
        base[rng.choice(168, 84, replace=False)] = True
        yield "84 h al azar (mismo patrón)", np.tile(base, n_weeks)
    for _ in range(1500):                                      # 84 horas al azar, distintas en cada semana
        m = np.zeros((n_weeks, 168), bool)
        for w in range(n_weeks):
            m[w, rng.choice(168, 84, replace=False)] = True
        yield "84 h al azar (cada semana)", m.ravel()
    for _ in range(500):                                       # días enteros al azar no da 50 %: 3,5 días = 7 medios días
        base = np.zeros(168, bool)
        for j in rng.choice(14, 7, replace=False):
            base[j * 12:(j + 1) * 12] = True
        yield "7 medios días al azar", np.tile(base, n_weeks)


def mask_aware_lp(load, pv, price, co2, m, b_co2, b_eur):
    """Plan que minimiza SOLO lo que se paga en las horas de la máscara (un agente que la conociera)."""
    n = len(load)
    w = np.where(m, 0.7 * co2 / b_co2[m].sum() + 0.3 * price / b_eur[m].sum(), 0.0)
    eye = sp.identity(n, format="csr")
    shift = sp.diags([np.ones(n - 1)], [-1], shape=(n, n), format="csr")
    # variables: c, d, g, s
    a_eq = sp.hstack([-ETA * eye, (1.0 / ETA) * eye, sp.csr_matrix((n, n)), eye - shift], format="csr")
    b_eq = np.zeros(n)
    b_eq[0] = CAP / 2
    a_ub = sp.hstack([eye, -eye, -eye, sp.csr_matrix((n, n))], format="csr")    # c - d - g <= -(load - pv)
    b_ub = -(load - pv)
    w = w / w[m].mean()                                        # pesos de orden 1 (el desempate queda muy por debajo)
    cost = np.concatenate([np.full(n, 1e-4), np.full(n, 1e-4), w, np.zeros(n)])
    bounds = [(0, POW)] * (2 * n) + [(0, None)] * n + [(0, CAP)] * n
    r = linprog(cost, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    assert r.status == 0, r.message
    # El plan se pasa por la física del entorno oficial (una sola acción por hora, recortada a la batería):
    # lo que sale es un episodio válido y sin infracciones, así que la nota es alcanzable de verdad.
    act, soc, g = r.x[:n] - r.x[n:2 * n], CAP / 2, np.zeros(n)
    for t in range(n):
        a = float(act[t])
        if a > 0:
            a = min(a, POW, max(0.0, (CAP - soc) / ETA) * (1 - 1e-12))
            soc += a * ETA
        elif a < 0:
            a = -min(-a, POW, max(0.0, soc * ETA) * (1 - 1e-12))
            soc += a / ETA
        g[t] = max(load[t] - pv[t] + a, 0.0)
    return g


def main() -> int:
    win = sys.argv[1] if len(sys.argv) > 1 else "val"
    d = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
    b_co2, b_eur = np.asarray(d["base_co2"], float), np.asarray(d["base_eur"], float)
    o = pd.read_csv(REPO / "results" / "hourly" / f"hard_{win}_óptimo__todo_el_futuro.csv")
    load, pv = o["load_kw"].to_numpy(float), o["pv_kw"].to_numpy(float)
    price, co2 = o["price_eur_kwh"].to_numpy(float), o["co2_kg_kwh"].to_numpy(float)
    base = np.maximum(load - pv, 0.0)
    assert abs((base * co2).sum() - b_co2.sum()) < 1e-3 * b_co2.sum(), "el óptimo y calcal no son el mismo episodio"
    orc = {"co2": (base - o["import_kw"].to_numpy(float)) * co2, "eur": (base - o["import_kw"].to_numpy(float)) * price}
    n = len(base)
    n_weeks = n // 168
    full = np.ones(n, bool)
    ags = {"v10": d["out"]["v10"], "v14": d["out"]["v14"], "óptimo": orc}
    print(f"== Ventana {win}: {n} h, {n_weeks} semanas. Episodio entero ==")
    for k, a in ags.items():
        s, c, e = score(a["co2"], a["eur"], b_co2, b_eur, full)
        print(f"  {k:7s} score {s:6.2f} | CO2 {c:6.2f} % | coste {e:6.2f} %")
    print(f"  objetivo (27,98 frente a la v10 en la web): score x{OBJ['score']:.3f}, CO2 x{OBJ['co2']:.3f}, coste x{OBJ['eur']:.3f}")

    print("== 1. Óptimo con todo el futuro / v10 en la mitad pública, por familia de máscara ==")
    rng = np.random.default_rng(0)
    rows = {}
    for fam, m in masks(n_weeks, rng):
        sv, cv, ev = score(ags["v10"]["co2"], ags["v10"]["eur"], b_co2, b_eur, m)
        so, co, eo = score(orc["co2"], orc["eur"], b_co2, b_eur, m)
        s4, _, _ = score(ags["v14"]["co2"], ags["v14"]["eur"], b_co2, b_eur, m)
        rows.setdefault(fam.split(" (fase")[0] if fam.startswith("bloques") else fam, []).append(
            (so / sv, co / cv, eo / ev, s4 / sv, sv, so))
    out = []
    for fam, r in rows.items():
        r = np.asarray(r)
        both = int(((r[:, 0] >= OBJ["score"]) & (r[:, 1] >= OBJ["co2"]) & (r[:, 2] >= OBJ["eur"])).sum())
        print(f"  {fam:32s} n={len(r):4d} | óptimo/v10: mín x{r[:, 0].min():.3f} med x{np.median(r[:, 0]):.3f} máx x{r[:, 0].max():.3f}"
              f" | CO2 máx x{r[:, 1].max():.3f} | coste máx x{r[:, 2].max():.3f} | llegan a x{OBJ['score']:.3f}: {int((r[:, 0] >= OBJ['score']).sum())}"
              f" (con las tres cifras: {both}) | v14/v10: x{r[:, 3].min():.3f} a x{r[:, 3].max():.3f}")
        out.append({"ventana": win, "familia": fam, "n": len(r), "ratio_min": r[:, 0].min(), "ratio_med": np.median(r[:, 0]),
                    "ratio_max": r[:, 0].max(), "co2_max": r[:, 1].max(), "coste_max": r[:, 2].max(),
                    "llegan": int((r[:, 0] >= OBJ["score"]).sum()), "llegan_tres": both,
                    "v10_pub_min": r[:, 4].min(), "v10_pub_max": r[:, 4].max()})

    print("== 1 bis. ¿Y un agente a medio camino entre la v10 y el óptimo? (84 h al azar en cada semana, 3.000 máscaras) ==")
    rng = np.random.default_rng(2)
    ms = np.zeros((3000, n), bool)
    for i in range(3000):
        for w in range(n_weeks):
            ms[i, w * 168 + rng.choice(168, 84, replace=False)] = True
    bc, be = ms @ b_co2, ms @ b_eur
    sv = 70.0 * (ms @ ags["v10"]["co2"]) / bc + 30.0 * (ms @ ags["v10"]["eur"]) / be
    print(f"  la v10 en la mitad pública: de {sv.min():.2f} a {sv.max():.2f} (desv. típica {sv.std():.2f}; entero {score(ags['v10']['co2'], ags['v10']['eur'], b_co2, b_eur, full)[0]:.2f})")
    for lam in (0.25, 0.5, 0.75, 1.0):
        mc = ags["v10"]["co2"] + lam * (orc["co2"] - ags["v10"]["co2"])
        me = ags["v10"]["eur"] + lam * (orc["eur"] - ags["v10"]["eur"])
        sm = 70.0 * (ms @ mc) / bc + 30.0 * (ms @ me) / be
        rr = sm / sv
        print(f"  {int(lam * 100):3d} % del camino al óptimo: público/v10 mediana x{np.median(rr):.3f}, desv. típica {rr.std():.3f}, "
              f"P(>= x{OBJ['score']:.3f}) = {100 * (rr >= OBJ['score']).mean():.1f} %")
        out.append({"ventana": win, "familia": f"mezcla {lam:.2f} con el óptimo, 84 h al azar", "n": 3000, "ratio_min": rr.min(),
                    "ratio_med": np.median(rr), "ratio_max": rr.max(), "co2_max": np.nan, "coste_max": np.nan,
                    "llegan": int((rr >= OBJ["score"]).sum()), "llegan_tres": -1, "v10_pub_min": sv.min(), "v10_pub_max": sv.max()})
    r14 = (70.0 * (ms @ ags["v14"]["co2"]) / bc + 30.0 * (ms @ ags["v14"]["eur"]) / be) / sv
    print(f"  v14/v10 en la mitad pública: mediana x{np.median(r14):.4f}, desv. típica {r14.std():.4f} (en la web: x{24.06 / 24.15:.4f})")

    print("== 2. Techo de un agente que conociera la máscara (LP que solo paga las horas públicas) ==")
    h = np.arange(168)
    rng = np.random.default_rng(1)
    rnd = np.zeros((n_weeks, 168), bool)
    for w in range(n_weeks):
        rnd[w, rng.choice(168, 84, replace=False)] = True
    cases = {"1.ª mitad de cada semana": np.tile(h < 84, n_weeks), "2.ª mitad de cada semana": np.tile(h >= 84, n_weeks),
             "horas pares": np.tile(h % 2 == 0, n_weeks), "84 h al azar (cada semana)": rnd.ravel()}
    for name, m in cases.items():
        g = mask_aware_lp(load, pv, price, co2, m, b_co2, b_eur)
        a = {"co2": (base - g) * co2, "eur": (base - g) * price}
        pub, priv, tot = (score(a["co2"], a["eur"], b_co2, b_eur, mm) for mm in (m, ~m, full))
        v_pub = score(ags["v10"]["co2"], ags["v10"]["eur"], b_co2, b_eur, m)
        o_pub = score(orc["co2"], orc["eur"], b_co2, b_eur, m)
        print(f"  {name:28s} v10 {v_pub[0]:6.2f} | óptimo honrado {o_pub[0]:6.2f} | con la máscara: público {pub[0]:6.2f} "
              f"(x{pub[0] / v_pub[0]:.2f}; CO2 {pub[1]:.2f} %, coste {pub[2]:.2f} %) | privado {priv[0]:7.2f} | entero {tot[0]:6.2f}")
        out.append({"ventana": win, "familia": "LP con máscara: " + name, "n": 1, "ratio_min": pub[0] / v_pub[0],
                    "ratio_med": pub[0] / v_pub[0], "ratio_max": pub[0] / v_pub[0], "co2_max": pub[1], "coste_max": pub[2],
                    "llegan": int(pub[0] / v_pub[0] >= OBJ["score"]), "llegan_tres": -1, "v10_pub_min": v_pub[0], "v10_pub_max": priv[0]})
    dst = REPO / "results" / "p1_hard" / f"fin_reglas_mascara_{win}.csv"
    pd.DataFrame(out).to_csv(dst, index=False)
    print(f"guardado: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
