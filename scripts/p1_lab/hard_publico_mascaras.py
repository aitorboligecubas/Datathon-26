"""¿Qué máscara de "50 % de cada semana" hace que el banco reproduzca lo que salió en la web para las 7 versiones?

Antes: python scripts/p1_lab/hard_publico_calibra.py <ventana>   (val, dev, 1-7...)
Para cada máscara se calcula, con cada versión, el % de CO2 y de coste ahorrado sobre las horas de la máscara, y se
compara el patrón entre versiones (diferencias frente a la v10) con el de la web.
"""
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "hourly"
VERS = ["v6", "v7", "v8", "v9", "v10", "v12", "v14"]
WEB_KG = np.array([13607.2, 13776.6, 13789.2, 13822.8, 13809.7, 13815.8, 13772.5])
WEB_EUR = np.array([24974.56, 25636.04, 25442.25, 25468.67, 25665.85, 25511.18, 25525.83])
BASE_KG, BASE_EUR = 60255.0, 94985.0
WEB_CO2 = 100 * WEB_KG / BASE_KG
WEB_COST = 100 * WEB_EUR / BASE_EUR
REF = VERS.index("v10")
web_vec = np.r_[0.7 * (WEB_CO2 - WEB_CO2[REF]), 0.3 * (WEB_COST - WEB_COST[REF])]      # en puntos de score
web_score = 0.7 * WEB_CO2 + 0.3 * WEB_COST

wins = [w for w in (sys.argv[1:] or ["val", "dev", "1-7", "3-9", "12-18", "15-21"]) if (OUT / f"calibra_{w}.pkl").exists()]
data = {w: pickle.load(open(OUT / f"calibra_{w}.pkl", "rb")) for w in wins}


def masks_for(n):
    hw = np.arange(n) % 168
    day, hour = hw // 24, hw % 24
    m = {"todo": np.ones(n, bool), "primera mitad (h 0-83)": hw < 84, "segunda mitad (h 84-167)": hw >= 84,
         "días pares": day % 2 == 0, "días impares": day % 2 == 1,
         "horas pares": hour % 2 == 0, "horas impares": hour % 2 == 1,
         "mañana (0-11 h)": hour < 12, "tarde (12-23 h)": hour >= 12}
    for b in (3, 4, 6, 12):
        m[f"bloques de {b} h (pares)"] = (hw // b) % 2 == 0
        m[f"bloques de {b} h (impares)"] = (hw // b) % 2 == 1
    return m


def vec(d, mask):
    co2 = np.array([100 * d["out"][v]["co2"][mask].sum() / d["base_co2"][mask].sum() for v in VERS])
    cost = np.array([100 * d["out"][v]["eur"][mask].sum() / d["base_eur"][mask].sum() for v in VERS])
    return co2, cost


rows = []
names = list(masks_for(168).keys())
for label in names:
    vs, scs = [], []
    for w in wins:
        d = data[w]
        mask = masks_for(len(d["base_co2"]))[label]
        co2, cost = vec(d, mask)
        vs.append(np.r_[0.7 * (co2 - co2[REF]), 0.3 * (cost - cost[REF])])
        scs.append(0.7 * co2 + 0.3 * cost)
    v, sc = np.mean(vs, axis=0), np.mean(scs, axis=0)
    keep = np.r_[[i for i in range(len(VERS)) if i != REF], [len(VERS) + i for i in range(len(VERS)) if i != REF]]
    corr = float(np.corrcoef(v[keep], web_vec[keep])[0, 1])
    dsc = sc - sc[REF]
    wsc = web_score - web_score[REF]
    others = [i for i in range(len(VERS)) if i != REF]
    corr_s = float(np.corrcoef(dsc[others], wsc[others])[0, 1])
    signs = int(sum(np.sign(dsc[i]) == np.sign(wsc[i]) for i in others))
    rows.append((corr, label, corr_s, signs, dsc, v))
print("Web (score frente a v10): " + "  ".join(f"{VERS[i]} {web_score[i] - web_score[REF]:+.2f}" for i in range(len(VERS))))
print(f"Ventanas del banco: {wins}\n")
print(f"{'máscara':28s} corr(CO2 y coste)  corr(score)  signos  | score frente a v10: " + "  ".join(VERS))
for corr, label, corr_s, signs, dsc, v in sorted(rows, key=lambda r: -r[0]):
    print(f"{label:28s} {corr:+.2f}              {corr_s:+.2f}         {signs}/6    | " + "  ".join(f"{x:+.2f}" for x in dsc))

# referencia: máscaras al azar (mitad de las horas de cada semana)
rng = np.random.default_rng(0)
cs = []
for _ in range(400):
    vs = []
    for w in wins:
        d = data[w]
        n = len(d["base_co2"])
        mask = np.zeros(n, bool)
        for s in range(0, n, 168):
            idx = np.arange(s, min(s + 168, n))
            mask[rng.choice(idx, len(idx) // 2, replace=False)] = True
        co2, cost = vec(d, mask)
        vs.append(np.r_[0.7 * (co2 - co2[REF]), 0.3 * (cost - cost[REF])])
    v = np.mean(vs, axis=0)
    keep = np.r_[[i for i in range(len(VERS)) if i != REF], [len(VERS) + i for i in range(len(VERS)) if i != REF]]
    cs.append(float(np.corrcoef(v[keep], web_vec[keep])[0, 1]))
cs = np.array(cs)
print(f"\nMáscaras al azar (400): correlación media {cs.mean():+.2f}, percentil 5 {np.percentile(cs, 5):+.2f}, percentil 95 {np.percentile(cs, 95):+.2f}, máxima {cs.max():+.2f}")
