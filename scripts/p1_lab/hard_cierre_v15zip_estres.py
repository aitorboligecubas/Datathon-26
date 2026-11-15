"""Cierre: ¿cuándo podría dispararse mal el detector de la v15 y cuánto costaría? (ZIP v15 frente a ZIP FINAL, val)

Uso: python scripts/p1_lab/hard_cierre_v15zip_estres.py <carpeta_final> <carpeta_v15>
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hard_cierre_v15zip_compara as C  # noqa: E402

H = C.H


def main():
    d_final, d_v15 = sys.argv[1], sys.argv[2]
    df = H.split_frame(H.hard_table(), "val")
    irr = df["irradiancia_wm2"].to_numpy(float)
    n = len(df)
    rng = np.random.default_rng(11)
    r = rng.random(n)

    def prev(t):
        return t - 1 if t > 0 else t

    def mezcla(obs, t):                 # media de la hora anterior y la actual (p. ej. última muestra de 5 min)
        obs["noves_dades_5min"]["irradiancia_wm2"] = float(0.5 * (irr[prev(t)] + irr[t]))

    def b_luego_a(obs, t):              # hora actual la primera mitad del episodio y hora anterior la segunda
        obs["noves_dades_5min"]["irradiancia_wm2"] = float(irr[t] if t < n // 2 else irr[prev(t)])

    def b_sensor_cero(obs, t):          # hora actual, pero el sensor marca 0 en el 5 % de las horas
        obs["noves_dades_5min"]["irradiancia_wm2"] = float(0.0 if r[t] < 0.05 else irr[t])

    def b_ruido(obs, t):                # hora actual con un 30 % de ruido multiplicativo
        obs["noves_dades_5min"]["irradiancia_wm2"] = float(irr[t] * max(0.0, 1.0 + 0.3 * (2 * r[t] - 1)))

    def a_luego_b(obs, t):
        obs["noves_dades_5min"]["irradiancia_wm2"] = float(irr[prev(t)] if t < n // 2 else irr[t])

    for nm, fn in (("mezcla anterior/actual", mezcla), ("B la 1a mitad y A la 2a", b_luego_a),
                   ("B con sensor a 0 el 5%", b_sensor_cero), ("B con ruido 30%", b_ruido),
                   ("A la 1a mitad y B la 2a", a_luego_b)):
        print("== IRRADIANCIA:", nm, flush=True)
        C.run(C.load_agent(d_final, "ag_final_d"), df, False, mutate=fn, label="final | " + nm)
        C.run(C.load_agent(d_v15, "ag_v15_d"), df, False, mutate=fn, label="v15   | " + nm)

    nan_mask = r < 0.3

    def irr_nan(obs, t):
        if nan_mask[t]:
            obs["noves_dades_5min"]["irradiancia_wm2"] = float("nan")

    def irr_falta(obs, t):
        if nan_mask[t]:
            obs["noves_dades_5min"].pop("irradiancia_wm2", None)

    def sin_meteo(obs, t):
        for k in list(obs["noves_dades_5min"]):
            if k not in ("ultim_consum_kw", "ultima_solar_kw"):
                obs["noves_dades_5min"].pop(k)

    def contador_cero_sem(obs, t):
        if (t // 168) in (0, 7):
            obs["noves_dades_5min"]["ultim_consum_kw"] = 0.0
            obs["noves_dades_5min"]["ultima_solar_kw"] = 0.0

    def solar_nan(obs, t):
        if nan_mask[t]:
            obs["noves_dades_5min"]["ultima_solar_kw"] = float("nan")

    for nm, fn in (("irr NaN 30%", irr_nan), ("irr ausente 30%", irr_falta), ("sin meteo", sin_meteo),
                   ("contador y solar a 0 en las semanas 1 y 8", contador_cero_sem), ("solar NaN 30%", solar_nan)):
        for now in (False, True):
            print("== DEFORMADO:", nm, "| meteo de la hora", "ACTUAL" if now else "anterior", flush=True)
            C.run(C.load_agent(d_v15, "ag_v15_c"), df, now, shadow=C.load_agent(d_final, "ag_final_c"), mutate=fn,
                  label="v15 conduce, final en sombra | " + nm + (" | B" if now else " | A"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
