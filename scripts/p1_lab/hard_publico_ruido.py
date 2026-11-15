"""¿Cuánto ruido mete el reparto público/privado al comparar dos variantes? Con los registros hora a hora del banco.
Dos repartos posibles: mitad de las HORAS al azar, o 6 SEMANAS enteras de 11."""
import pickle, sys, itertools
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "hourly"
OUT.mkdir(parents=True, exist_ok=True)
import numpy as np
rng = np.random.default_rng(0)
for win in ("val", "dev", "1-7"):
    if not (OUT / f"publico_por_mes_{win}.pkl").exists():     # antes: python scripts/p1_lab/hard_publico_por_mes.py <ventana>
        continue
    d = pickle.load(open(str(OUT / f"publico_por_mes_{win}.pkl"), "rb"))
    out, base, df = d["out"], d["base"], d["df"]
    n = len(df)
    week = (np.arange(n) // 168)
    def score(name, mask):
        return 70 * out[name].co2.to_numpy()[mask].sum() / base.co2.to_numpy()[mask].sum() + 30 * out[name].eur.to_numpy()[mask].sum() / base.eur.to_numpy()[mask].sum()
    allm = np.ones(n, bool)
    print(f"== {win}: {n} h | score completo: " + " | ".join(f"{k} {score(k, allm):.3f}" for k in out))
    for a, b in (("z10", "z14"), ("v12", "z10"), ("z10", "z10_sin_semilla")):
        full = score(a, allm) - score(b, allm)
        hours = []
        for _ in range(2000):
            m = np.zeros(n, bool); m[rng.choice(n, n // 2, replace=False)] = True
            hours.append(score(a, m) - score(b, m))
        weeks = []
        ids = sorted(set(week))
        for combo in itertools.combinations(ids, len(ids) // 2 + (len(ids) % 2)):
            m = np.isin(week, combo)
            weeks.append(score(a, m) - score(b, m))
        hours, weeks = np.array(hours), np.array(weeks)
        print(f"   {a:4s} - {b:16s}: completo {full:+.3f} | mitad de horas al azar: media {hours.mean():+.3f}, desv. {hours.std():.3f}, P(<0) {100*(hours<0).mean():.0f} %, P(<= -0.04) {100*(hours<=-0.04).mean():.1f} % | "
              f"6 semanas enteras: media {weeks.mean():+.3f}, desv. {weeks.std():.3f}, P(<0) {100*(weeks<0).mean():.0f} %, P(<= -0.04) {100*(weeks<=-0.04).mean():.1f} %")
