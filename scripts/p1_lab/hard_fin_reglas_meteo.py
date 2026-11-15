"""Revisión de REGLAS Y ENTORNO: ¿la meteo de la hora anterior (que el agente lee y no usa) ayuda a prever el consumo?

Owner: P1. NO se empaqueta. Solo train. Regresión lineal por antelación, ajustada en los días 1-17 y medida en los
días 18-24 de cada mes, con y sin la meteo de la hora anterior. (Para la solar y el mercado ya estaba medido:
results/p1_hard/solar_notas.md y mercado_notas.md.)

    python scripts/p1_lab/hard_fin_reglas_meteo.py
"""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
import p1_hard as B  # noqa: E402


def main() -> int:
    df = B.hard_table().set_index("timestamp").asfreq("1h")
    hr = df.index.hour.to_numpy()
    wk = (df.index.dayofweek.to_numpy() >= 5).astype(int)
    onehot = np.zeros((len(df), 48))
    onehot[np.arange(len(df)), hr + 24 * wk] = 1.0
    met = [c for c in ("irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms") if c in df]
    print("columnas de meteo:", met)
    for lead in (0, 1, 3, 6, 12):
        y = df["load_kw"].shift(-lead)
        hr_t = (hr + lead) % 24
        base = np.column_stack([onehot[np.arange(len(df)), :][:, :] if lead == 0 else np.roll(onehot, -lead, axis=0),
                                df["load_kw"].shift(1), df["load_kw"].shift(24 - lead), df["load_kw"].shift(168 - lead)])
        m_prev = df[met].shift(1)
        extra = np.column_stack([m_prev.to_numpy(), (m_prev["temp_ambient_c"] ** 2).to_numpy(),
                                 (m_prev["temp_ambient_c"] - df["temp_ambient_c"].shift(25)).to_numpy()])
        full = np.column_stack([base, extra])
        ok = np.isfinite(full).all(axis=1) & np.isfinite(y.to_numpy())
        day = df.index.day.to_numpy()
        tr, te = ok & (day <= 17), ok & (day >= 18) & (day <= 24)
        dayh = te & (hr_t >= 6) & (hr_t <= 22)            # de 23 a 5 h el contador está congelado
        out = []
        for x in (base, full):
            coef, *_ = np.linalg.lstsq(x[tr], y.to_numpy()[tr], rcond=None)
            err = y.to_numpy() - x @ coef
            out.append((float(np.sqrt((err[te] ** 2).mean())), float(np.sqrt((err[dayh] ** 2).mean()))))
        print(f"  antelación {lead:2d} h | RMSE fuera de muestra sin meteo {out[0][0]:6.1f} kW, con meteo {out[1][0]:6.1f} kW "
              f"({100 * (out[1][0] / out[0][0] - 1):+.1f} %) | de 6 a 22 h: {out[0][1]:6.1f} -> {out[1][1]:6.1f} kW "
              f"({100 * (out[1][1] / out[0][1] - 1):+.1f} %) | n = {int(tr.sum())} / {int(te.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
