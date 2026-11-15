"""Cierre: peor caso de disparo "falso" persistente del detector de la v15. Mundo inventado: el contador (consumo y
solar) llega con una hora MÁS de retraso (hora t-2) y la meteo es de la hora anterior (t-1). El detector ve lo mismo
que en el mundo B, pero la irradiancia no es de la hora actual.

Uso: python scripts/p1_lab/hard_cierre_v15zip_retraso.py <carpeta_final> <carpeta_v15>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hard_cierre_v15zip_compara as C  # noqa: E402

H = C.H


def main():
    d_final, d_v15 = sys.argv[1], sys.argv[2]
    df = H.split_frame(H.hard_table(), "val")
    load_ = df["load_kw"].to_numpy(float); pv = df["pv_kw"].to_numpy(float)

    def retraso(obs, t):
        k = max(t - 2, 0)
        obs["noves_dades_5min"]["ultim_consum_kw"] = float(load_[k])
        obs["noves_dades_5min"]["ultima_solar_kw"] = float(pv[k])

    print("== CONTADOR CON UNA HORA MÁS DE RETRASO (t-2), meteo de t-1", flush=True)
    C.run(C.load_agent(d_final, "ag_final_r"), df, False, mutate=retraso, label="final | contador t-2")
    C.run(C.load_agent(d_v15, "ag_v15_r"), df, False, mutate=retraso, label="v15   | contador t-2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
