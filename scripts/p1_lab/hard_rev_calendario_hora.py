"""Revisión "calendario": el cambio de hora en las semanas del test (26/10/2025 y 29/03/2026). NO se empaqueta.
Episodio con el calendario del test; se quita la fila del 29/03 02:00 y se repite la del 26/10 02:00.
Compara el agente actual con un parche: SolarCand.learn trata un salto de 0 o 2 horas como horas seguidas."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hard_ataque_comun as c  # noqa: E402
from battery import hard_solar as hs  # noqa: E402


def parche(pol):
    nl = pol.netload
    orig = nl.learn

    def learn(obs):
        ts = obs.timestamp
        if ts is not None and nl.last_value is not None and (ts.value - nl.last_value) in (0, 2 * hs.HOUR_NS):
            nl.last_value = ts.value - hs.HOUR_NS       # hora repetida o ausente: sigue siendo la hora siguiente
        return orig(obs)

    nl.learn = learn


def main() -> int:
    df, origen = c.episodio_test(nov="omitir")
    pm, ps = c.priors(origen)
    ts = pd.DatetimeIndex(df.timestamp)
    d2 = df[ts != pd.Timestamp("2026-03-29 02:00")]
    k = int(np.flatnonzero(pd.DatetimeIndex(d2.timestamp) == pd.Timestamp("2025-10-26 02:00"))[0])
    d2 = pd.concat([d2.iloc[:k + 1], d2.iloc[k:k + 1], d2.iloc[k + 1:]], ignore_index=True)
    rows = []
    for nombre, datos, fix in (("sin cambio de hora", df, False), ("con cambio de hora, actual", d2, False),
                               ("con cambio de hora, parche", d2, True)):
        a = c.agente(pm, ps)
        if fix:
            parche(a.policy)
        r = c.simular(a, datos)
        lg = r["log"]
        t = pd.DatetimeIndex(lg.timestamp)
        dia = ((t >= "2026-03-29") & (t < "2026-03-30")) | ((t >= "2025-10-26") & (t < "2025-10-27"))
        rows.append({"caso": nombre, "h": len(datos), "score": r["score"], "infr": r["infr"], "exc": r["excepciones"],
                     "semanas": a.policy.n_blocks, "vert_desc": r["vert_descarga"],
                     "vert_desc_dias_cambio": float(lg[dia & (lg.action_kw < -1e-6)].export_kw.sum())})
        print(pd.DataFrame(rows[-1:]).round(4).to_string(index=False), flush=True)
    pd.DataFrame(rows).to_csv(c.REPO / "results" / "p1_hard" / "rev_calendario_hora.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
