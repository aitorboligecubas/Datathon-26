"""Ataque 3 al agente del HARD MODE: el calendario. NO se empaqueta.

Owner: P1. El agente cree que el test son los últimos 7 días de cada mes y que acaba en julio o agosto de
2026 (battery.hard.LAST_MONTHS). Aquí se mide cuánto score se pierde cuando eso no es verdad.

    python scripts/p1_lab/hard_ataque_calendario.py

Todos los episodios llevan el calendario del test (hard_ataque_comun.episodio_test). Variantes del agente:
    actual        el de src/, tal cual
    solo_agosto   LAST_MONTHS = ((2026, 8),)            (julio deja de ser "último mes")
    sin_final     LAST_MONTHS = ()                       (nunca sabe que el test acaba)
    informado     conoce las fechas reales de las próximas 24 filas del episodio (techo del calendario)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
import battery.hard as hard  # noqa: E402

LAST_SRC = hard.LAST_MONTHS


class Informada(hard.HardPolicy):
    """Sabe qué filas vienen después (como si el entorno diera las fechas de las próximas 24 horas)."""
    fechas = None

    def horizon_times(self, obs):
        return list(self.fechas[self.t:self.t + self.horizon])


def correr(df, pm, ps, variante: str) -> dict:
    hard.LAST_MONTHS = {"actual": LAST_SRC, "informado": LAST_SRC, "solo_agosto": ((2026, 8),),
                        "sin_final": ()}.get(variante, LAST_SRC)
    if variante.startswith("ultimo="):
        y, m = variante.split("=")[1].split("-")
        hard.LAST_MONTHS = ((int(y), int(m)),)
    a = c.agente(pm, ps)
    if variante == "informado":
        a.policy.__class__ = Informada
        a.policy.fechas = list(df.timestamp)
    try:
        r = c.simular(a, df)
    finally:
        hard.LAST_MONTHS = LAST_SRC
    return r


def main() -> int:
    full, origen = c.episodio_test("copia")
    pm, ps = c.priors(origen)
    sin_nov, _ = c.episodio_test("omitir")
    casos = [
        ("A. test completo (12 semanas, acaba en agosto)", full, ["actual", "solo_agosto", "sin_final", "informado"]),
        ("B. mitad pública sola (sep-feb, acaba en febrero)", full.iloc[:6 * c.WEEK].reset_index(drop=True),
         ["actual", "ultimo=2026-2", "informado"]),
        ("C. mitad privada sola (mar-ago)", full.iloc[6 * c.WEEK:].reset_index(drop=True),
         ["actual", "solo_agosto", "informado"]),
        ("D. falta una semana (de octubre se salta a diciembre)", sin_nov, ["actual", "solo_agosto", "informado"]),
        ("E. prueba rápida de 48 pasos", full.iloc[:48].reset_index(drop=True), ["actual", "informado"]),
        ("F. fechas de otro año (todo un año antes)", full.assign(timestamp=full.timestamp - pd.DateOffset(years=1)),
         ["actual", "informado"]),
    ]
    rows = []
    for nombre, df, variantes in casos:
        base = None
        for v in variantes:
            r = correr(df, pm, ps, v)
            if base is None:
                base = r["score"]
            rows.append({"caso": nombre, "variante": v, "horas": len(df), "score": r["score"],
                         "dif_vs_actual": r["score"] - base, "infr": r["infr"], "soc_final_kwh": r["soc_final"],
                         "vert_descarga": r["vert_descarga"], "vert_solar": r["vert_solar"]})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out.round(3).to_string(index=False))
    out_dir = c.REPO / "results" / "p1_hard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "ataque_calendario.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
