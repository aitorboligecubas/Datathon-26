"""Encargo "calibracion" (ronda 3), punto 4: si la hipótesis M es cierta (el banco acierta en el episodio completo y la
web enseña la mitad de las horas), ¿qué nota PRIVADA (las otras horas) cabe esperar de v12 y v14 frente a la v10,
sabiendo lo que salió en el público? Se sortean máscaras, se quedan las que dan en el público algo parecido a la web
y se mira el privado (la máscara complementaria) de esas. NO se empaqueta. Owner: P1.

    python scripts/p1_lab/hard_r3_calibracion_privado.py
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.argv = [sys.argv[0], "200"]
import hard_r3_calibracion_mascaras as K  # noqa: E402  (reutiliza familias y datos; imprime su tabla con 200 máscaras)

N = 4000
V = K.VERS
i10, i12, i14, i9, i6, i7 = (V.index(v) for v in ("v10", "v12", "v14", "v9", "v6", "v7"))
out = []
print("\n\n4. PRIVADO ESPERADO SI M ES CIERTA (frente a la v10). 'cond.': solo las máscaras cuyo público se parece a la web")
print("   (v12 a menos de 0,06 de -0,042 y v14 a menos de 0,20 de -0,087).")
rows = []
for name, fam in K.FAMILIES:
    if "casos" in name:
        continue
    pub, pri = [], []
    for w in K.wins:
        d = K.data[w]
        M = fam(d["W"] * 168, N)[:, d["idx"]]
        _, _, a = K.deltas(d, M)
        _, _, b = K.deltas(d, ~M)
        pub.append(a); pri.append(b)
    pub, pri = np.concatenate(pub, axis=1), np.concatenate(pri, axis=1)
    near = (np.abs(pub[i12] - K.WEB_DSC[i12]) < 0.06) & (np.abs(pub[i14] - K.WEB_DSC[i14]) < 0.20)
    r = {"familia": name, "sigma v6": pub[i6].std(), "sigma v7": pub[i7].std(), "sigma v14-v12": (pub[i14] - pub[i12]).std(),
         "n cond.": int(near.sum()), "frac. cond.": near.mean()}
    for v, i in (("v12", i12), ("v14", i14)):
        x = pri[i][near]
        r[f"priv. {v} cond. media"] = x.mean() if len(x) else np.nan
        r[f"priv. {v} cond. p10"] = np.percentile(x, 10) if len(x) else np.nan
        r[f"priv. {v} cond. p90"] = np.percentile(x, 90) if len(x) else np.nan
        r[f"P(priv. {v} > v10)"] = (x > 0).mean() if len(x) else np.nan
    x = (pri[i14] - pri[i12])[near]
    r["P(priv. v14 > v12)"] = (x > 0).mean() if len(x) else np.nan
    x = np.maximum(pri[i14], pri[i12])[near]
    r["E[max(v14,v12)]"] = x.mean() if len(x) else np.nan
    x = np.maximum(pri[i14], 0.0)[near]
    r["E[max(v14,v10)]"] = x.mean() if len(x) else np.nan
    x = np.maximum(pri[i12], 0.0)[near]
    r["E[max(v12,v10)]"] = x.mean() if len(x) else np.nan
    rows.append(r)
df = pd.DataFrame(rows)
pd.set_option("display.width", 330, "display.max_colwidth", 55, "display.max_columns", 40)
print(df.round(3).to_string(index=False))
df.to_csv(K.OUT / "r3_calibracion_privado.csv", index=False)
# diferencia media de acción, en valor absoluto, frente a la v10
print("\n   Diferencia media de acción frente a la v10, en valor absoluto (kW por hora) y horas con más de 100 kW de diferencia:")
for v in ("v8", "v9", "v12", "v14"):
    dif = np.concatenate([np.abs(K.data[w]["out"][v]["action"] - K.data[w]["out"]["v10"]["action"]) for w in K.wins])
    print(f"   {v}: {dif.mean():6.1f} kW   {100 * (dif > 100).mean():5.1f} % de las horas")
