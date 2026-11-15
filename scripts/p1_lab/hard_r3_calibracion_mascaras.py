"""Encargo "calibracion" (ronda 3), puntos 1 y 2: ¿puede una máscara de "50 % de cada semana" explicar que en la web
v8, v9, v12 y v14 salgan todas por debajo de la v10, cuando en el banco (episodio completo) salen por encima?

    python scripts/p1_lab/hard_r3_calibracion_mascaras.py            # usa los calibra_<ventana>.pkl que existan

Para cada familia de máscaras (mitad de las horas de cada semana) y cada ventana del banco se sortean máscaras y se
calcula, como hace el código oficial (evaluate_results(mask=...)), el % de CO2 y de coste ahorrado sobre las horas de
la máscara. Se cuenta con qué frecuencia el banco reproduce lo que salió en la web. NO se empaqueta. Owner: P1.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
HOURLY = REPO / "results" / "hourly"
OUT = REPO / "results" / "p1_hard"
VERS = ["v6", "v7", "v8", "v9", "v10", "v12", "v14"]
WEB_KG = np.array([13607.2, 13776.6, 13789.2, 13822.8, 13809.7, 13815.8, 13772.5])
WEB_EUR = np.array([24974.56, 25636.04, 25442.25, 25468.67, 25665.85, 25511.18, 25525.83])
BASE_KG, BASE_EUR = 60255.0, 94985.0
REF = VERS.index("v10")
WEB_DCO2 = 100 * (WEB_KG - WEB_KG[REF]) / BASE_KG            # puntos porcentuales frente a la v10
WEB_DCOST = 100 * (WEB_EUR - WEB_EUR[REF]) / BASE_EUR
WEB_DSC = 0.7 * WEB_DCO2 + 0.3 * WEB_DCOST
FOUR = [VERS.index(v) for v in ("v8", "v9", "v12", "v14")]
N_MASKS = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

wins = [w for w in ("val", "dev", "1-7", "3-9", "12-18", "15-21") if (HOURLY / f"calibra_{w}.pkl").exists()]
data = {w: pickle.load(open(HOURLY / f"calibra_{w}.pkl", "rb")) for w in wins}
rng = np.random.default_rng(20261115)


def grid_index(d):
    """Cada hora de la ventana -> (semana, hora dentro de la semana). Las ventanas no son múltiplos exactos de 168 h
    (no hay noviembre y algún mes está incompleto), así que se usa la fecha y no la posición."""
    ts = pd.DatetimeIndex(d["timestamp"])
    wk = pd.factorize(ts.year * 12 + ts.month)[0]
    first = pd.Series(ts).groupby(wk).transform("min")
    hw = np.clip(((ts - pd.DatetimeIndex(first)) / pd.Timedelta(hours=1)).to_numpy().astype(int), 0, 167)
    return wk, hw, int(wk.max()) + 1


for _d in data.values():
    _d["wk"], _d["hw"], _d["W"] = grid_index(_d)
    _d["idx"] = _d["wk"] * 168 + _d["hw"]


# ------------------------------------------------------------------------------------------ familias de máscaras
def tile(pattern, n):
    return np.tile(pattern, n // 168 + 1)[:n]


def fam_horas_sueltas(n, m):
    out = np.zeros((m, n), bool)
    for s in range(0, n, 168):
        k = min(168, n - s)
        out[:, s:s + k] = np.argsort(rng.random((m, k)), axis=1) < k // 2
    return out


def fam_horas_patron(n, m):
    pat = np.argsort(rng.random((m, 168)), axis=1) < 84
    return np.array([tile(p, n) for p in pat])


def dias(m, weeks):
    """(m, weeks, 7) bool: 3 o 4 días enteros de cada semana."""
    k = rng.integers(3, 5, size=(m, weeks, 1))
    return np.argsort(rng.random((m, weeks, 7)), axis=2) < k


def fam_dias(n, m):
    w = n // 168
    return np.repeat(dias(m, w), 24, axis=2).reshape(m, w * 168)[:, :n]


def fam_dias_patron(n, m):
    return np.array([tile(p, n) for p in np.repeat(dias(m, 1)[:, 0, :], 24, axis=1)])


def fam_media_semana(n, m):
    w = n // 168
    start = rng.integers(0, 168, size=(m, w, 1))
    hw = np.arange(168)[None, None, :]
    return (((hw - start) % 168) < 84).reshape(m, w * 168)[:, :n]


def fam_media_semana_patron(n, m):
    hw = np.arange(168)
    return np.array([tile(((hw - s) % 168) < 84, n) for s in range(168)])


def fam_alternos(n, m):
    hw = np.arange(168)
    return np.array([tile(((hw + ph) // b) % 2 == 0, n) for b in (1, 2, 3, 4, 6, 12) for ph in range(2 * b)])


def fam_paridad(n, m):
    hw = np.arange(168)
    return np.array([tile(hw % 2 == 0, n), tile(hw % 2 == 1, n)])


def fam_hora_del_dia(n, m):
    pat = np.argsort(rng.random((m, 24)), axis=1) < 12
    return np.array([np.tile(p, n // 24 + 1)[:n] for p in pat])


def fam_bloques(b):
    def f(n, m):
        w, nb = n // 168, 168 // b
        pick = np.argsort(rng.random((m, w, nb)), axis=2) < nb // 2
        return np.repeat(pick, b, axis=2).reshape(m, w * 168)[:, :n]
    return f


FAMILIES = [
    ("horas sueltas (cada semana las suyas)", fam_horas_sueltas),
    ("horas sueltas (mismo patrón semanal)", fam_horas_patron),
    ("bloques de 6 h al azar", fam_bloques(6)),
    ("bloques de 12 h al azar", fam_bloques(12)),
    ("días enteros (cada semana los suyos)", fam_dias),
    ("días enteros (mismo patrón semanal)", fam_dias_patron),
    ("media semana seguida (cada semana la suya)", fam_media_semana),
    ("media semana seguida (mismo corte; 168 casos)", fam_media_semana_patron),
    ("bloques alternos de 1-12 h (56 casos)", fam_alternos),
    ("horas pares / impares (2 casos)", fam_paridad),
    ("12 horas del día fijas (las mismas todos los días)", fam_hora_del_dia),
]


def deltas(d, M):
    """Para un lote de máscaras M (m, n): diferencia frente a la v10 de CO2 %, coste % y score. Devuelve (7, m) x 3."""
    Mf = M.astype(float)
    bc, be = Mf @ d["base_co2"], Mf @ d["base_eur"]
    co2 = np.array([100 * (Mf @ d["out"][v]["co2"]) / bc for v in VERS])
    cost = np.array([100 * (Mf @ d["out"][v]["eur"]) / be for v in VERS])
    dco2, dcost = co2 - co2[REF], cost - cost[REF]
    return dco2, dcost, 0.7 * dco2 + 0.3 * dcost


lines = []


def say(s=""):
    print(s, flush=True)
    lines.append(s)


say("WEB, frente a la v10 (CO2 en puntos porcentuales, coste en puntos porcentuales, score):")
for i in FOUR:
    say(f"   {VERS[i]:4s} CO2 {WEB_DCO2[i]:+.3f}  coste {WEB_DCOST[i]:+.3f}  score {WEB_DSC[i]:+.3f}")
say(f"\nVentanas del banco: {wins}")
say("\nBANCO, episodio completo, frente a la v10 (CO2 pp / coste pp / score):")
full_rows = []
for w in wins:
    d = data[w]
    dco2, dcost, dsc = deltas(d, np.ones((1, len(d["base_co2"])), bool))
    say(f"   {w:6s} " + "  ".join(f"{VERS[i]} {dco2[i, 0]:+.3f}/{dcost[i, 0]:+.3f}/{dsc[i, 0]:+.3f}" for i in FOUR))
    full_rows.append([dco2[FOUR, 0], dcost[FOUR, 0], dsc[FOUR, 0]])
fr = np.mean(full_rows, axis=0)
say("   media  " + "  ".join(f"{VERS[i]} {fr[0][j]:+.3f}/{fr[1][j]:+.3f}/{fr[2][j]:+.3f}" for j, i in enumerate(FOUR)))

say(f"\n1. FAMILIAS DE MÁSCARAS ({N_MASKS} máscaras por familia y ventana, {len(wins)} ventanas)")
say("   P(4<v10): v8, v9, v12 y v14 TODAS por debajo de la v10 en el público.")
say("   P(magn.): además, CO2 de las cuatro a menos de 0,10 pp de la v10 y coste entre -0,05 y -0,40 pp (lo de la web).")
say("   P(v14<=web): la v14 sale tan mal o peor que en la web (-0,087).  sigma: desviación del público de la v14 frente a la v10.")
say("   z(v14): cuántas sigmas separan la web (-0,087) de la media del banco con esa familia.")
say("   D2: distancia de Mahalanobis de la web (8 números: CO2 y coste de las cuatro) a la nube del banco; p(D2): fracción de máscaras tan lejos o más.")
tab = []
for name, fam in FAMILIES:
    acc = {k: [] for k in ("all4", "mag", "both", "v14web", "dsc14", "dsc12", "dsc9", "dsc8", "vec")}
    per_win = []
    for w in wins:
        d = data[w]
        M = fam(d["W"] * 168, N_MASKS)[:, d["idx"]]
        dco2, dcost, dsc = deltas(d, M)
        a4 = (dsc[FOUR] < 0).all(axis=0)
        mag = a4 & (np.abs(dco2[FOUR]) <= 0.10).all(axis=0) & (dcost[FOUR] <= -0.05).all(axis=0) & (dcost[FOUR] >= -0.40).all(axis=0)
        acc["all4"].append(a4); acc["mag"].append(mag)
        acc["both"].append((dsc[VERS.index("v12")] < 0) & (dsc[VERS.index("v14")] < 0))
        acc["v14web"].append(dsc[VERS.index("v14")] <= WEB_DSC[VERS.index("v14")])
        for v in ("v8", "v9", "v12", "v14"):
            acc["dsc" + v[1:]].append(dsc[VERS.index(v)])
        acc["vec"].append(np.r_[0.7 * dco2[FOUR], 0.3 * dcost[FOUR]].T)          # (m, 8)
        per_win.append(float(a4.mean()))
    cat = {k: np.concatenate(v) for k, v in acc.items()}
    X = cat["vec"]
    mu, cov = X.mean(axis=0), np.cov(X.T) + 1e-9 * np.eye(8)
    webv = np.r_[0.7 * WEB_DCO2[FOUR], 0.3 * WEB_DCOST[FOUR]]
    inv = np.linalg.pinv(cov)
    d2_web = float((webv - mu) @ inv @ (webv - mu))
    d2_all = np.einsum("ij,jk,ik->i", X - mu, inv, X - mu)
    p_d2 = float((d2_all >= d2_web).mean())
    s14 = cat["dsc14"]
    row = {"familia": name, "n": len(s14), "P(4<v10)": cat["all4"].mean(), "P(magn.)": cat["mag"].mean(), "P(v12 y v14<v10)": cat["both"].mean(),
           "P(v14<=web)": cat["v14web"].mean(), "media v14": s14.mean(), "sigma v14": s14.std(), "z(v14)": (WEB_DSC[VERS.index("v14")] - s14.mean()) / max(s14.std(), 1e-9),
           "media v12": cat["dsc12"].mean(), "sigma v12": cat["dsc12"].std(), "media v9": cat["dsc9"].mean(), "sigma v9": cat["dsc9"].std(),
           "media v8": cat["dsc8"].mean(), "sigma v8": cat["dsc8"].std(), "D2 web": d2_web, "p(D2)": p_d2,
           "P(4<v10) mín-máx por ventana": f"{min(per_win):.3f}-{max(per_win):.3f}"}
    tab.append(row)
df = pd.DataFrame(tab)
pd.set_option("display.width", 320, "display.max_colwidth", 60, "display.max_columns", 30)
say(df.round(4).to_string(index=False))
df.to_csv(OUT / "r3_calibracion_familias.csv", index=False)

# ------------------------------------------------------------------------------------------ 2. ¿en qué horas gana cada una?
say("\n2. ¿EN QUÉ HORAS GANA LA v10? Aportación de cada hora del día a la diferencia de score del episodio completo")
say("   (media de las ventanas; la suma de la columna es la diferencia del episodio completo). Acción media en kW (+ carga).")
H = np.zeros((len(wins), 24, 8))
par = np.zeros((len(wins), 2, 4))
dow = np.zeros((len(wins), 7, 2))
pos = np.zeros((len(wins), 7, 2))
for iw, w in enumerate(wins):
    d = data[w]
    ts = pd.DatetimeIndex(d["timestamp"])
    hour, n = ts.hour.to_numpy(), len(ts)
    Bc, Be = d["base_co2"].sum(), d["base_eur"].sum()
    o = d["out"]
    for j, v in enumerate(("v9", "v12", "v14")):
        c = 70 * (o[v]["co2"] - o["v10"]["co2"]) / Bc
        e = 30 * (o[v]["eur"] - o["v10"]["eur"]) / Be
        for h in range(24):
            H[iw, h, 2 * j] = c[hour == h].sum()
            H[iw, h, 2 * j + 1] = e[hour == h].sum()
        if v in ("v12", "v14"):
            jj = 0 if v == "v12" else 1
            t = d["hw"]
            par[iw, 0, 2 * jj], par[iw, 1, 2 * jj] = (c + e)[hour % 2 == 0].sum(), (c + e)[hour % 2 == 1].sum()
            par[iw, 0, 2 * jj + 1], par[iw, 1, 2 * jj + 1] = (c + e)[t % 168 < 84].sum(), (c + e)[t % 168 >= 84].sum()
            for k in range(7):
                dow[iw, k, jj] = (c + e)[ts.dayofweek.to_numpy() == k].sum()
                pos[iw, k, jj] = (c + e)[(t % 168) // 24 == k].sum()
    for h in range(24):
        H[iw, h, 6] = o["v10"]["action"][hour == h].mean()
        H[iw, h, 7] = o["v14"]["action"][hour == h].mean()
Hm = H.mean(axis=0)
say("   hora | v9-v10: CO2  coste | v12-v10: CO2  coste | v14-v10: CO2  coste  total | acción v10  acción v14  dif")
for h in range(24):
    say(f"   {h:4d} |      {Hm[h, 0]:+.3f} {Hm[h, 1]:+.3f} |       {Hm[h, 2]:+.3f} {Hm[h, 3]:+.3f} |       {Hm[h, 4]:+.3f} {Hm[h, 5]:+.3f} {Hm[h, 4] + Hm[h, 5]:+.3f} |"
        f"   {Hm[h, 6]:+7.0f}     {Hm[h, 7]:+7.0f}  {Hm[h, 7] - Hm[h, 6]:+6.0f}")
say(f"   suma |      {Hm[:, 0].sum():+.3f} {Hm[:, 1].sum():+.3f} |       {Hm[:, 2].sum():+.3f} {Hm[:, 3].sum():+.3f} |       {Hm[:, 4].sum():+.3f} {Hm[:, 5].sum():+.3f} {Hm[:, 4:6].sum():+.3f}")
pd.DataFrame(Hm, columns=["v9_co2", "v9_coste", "v12_co2", "v12_coste", "v14_co2", "v14_coste", "accion_v10", "accion_v14"]).to_csv(OUT / "r3_calibracion_por_hora.csv", index_label="hora")
pm = par.mean(axis=0)
say("\n   Aportación al episodio completo (el público de esa mitad sería ~el doble):")
say(f"   horas pares:   v12-v10 {pm[0, 0]:+.3f}   v14-v10 {pm[0, 2]:+.3f}        horas impares:  v12-v10 {pm[1, 0]:+.3f}   v14-v10 {pm[1, 2]:+.3f}")
say(f"   primera mitad de la semana: v12-v10 {pm[0, 1]:+.3f}   v14-v10 {pm[0, 3]:+.3f}   segunda mitad: v12-v10 {pm[1, 1]:+.3f}   v14-v10 {pm[1, 3]:+.3f}")
dm, pp = dow.mean(axis=0), pos.mean(axis=0)
say("   por día de la semana (L..D):  v12-v10 " + " ".join(f"{x:+.3f}" for x in dm[:, 0]) + "   v14-v10 " + " ".join(f"{x:+.3f}" for x in dm[:, 1]))
say("   por día de la ventana (1.º..7.º): v12-v10 " + " ".join(f"{x:+.3f}" for x in pp[:, 0]) + "   v14-v10 " + " ".join(f"{x:+.3f}" for x in pp[:, 1]))

# ¿qué horas del día tienen las máscaras "12 horas del día fijas" que reproducen la web?
say("\n   Máscaras '12 horas del día fijas' que reproducen la web (las cuatro por debajo de la v10): frecuencia con que entra cada hora")
inc, tot = np.zeros(24), 0
for w in wins:
    d = data[w]
    pat = np.argsort(rng.random((N_MASKS, 24)), axis=1) < 12
    M = pat[:, pd.DatetimeIndex(d["timestamp"]).hour.to_numpy()]
    _, _, dsc = deltas(d, M)
    ok = (dsc[FOUR] < 0).all(axis=0)
    inc += pat[ok].sum(axis=0)
    tot += int(ok.sum())
if tot:
    say("   hora:  " + " ".join(f"{h:4d}" for h in range(24)))
    say("   frec.: " + " ".join(f"{x:4.2f}" for x in inc / tot) + f"    ({tot} máscaras)")
(OUT / "r3_calibracion_mascaras.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
