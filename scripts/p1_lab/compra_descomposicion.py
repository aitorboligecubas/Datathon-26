"""¿De dónde viene la pérdida frente al óptimo en un episodio con noviembre a cero? NO se empaqueta.

    python scripts/p1_lab/compra_descomposicion.py                      # agente actual, banco alineado
    python scripts/p1_lab/compra_descomposicion.py --banco estandar
    python scripts/p1_lab/compra_descomposicion.py --agent scripts/p1_lab/cand_compra.py

Para cada episodio nov0 de la suite dev parte la distancia al óptimo en cuatro trozos, comparando al agente
con "el óptimo a partir de aquí" (el LP con todo el futuro conocido, desde la carga que el agente lleva):
    llegada   lo que ya estaba perdido al empezar la semana sin datos (llegar con la batería cargada)
    hora 1    lo que se pierde en la primera hora de esa semana, cuando aún no se sabe que viene a 0
    compra    lo que se pierde durante la semana: cuándo y cuánto se compra
    resto     lo que se pierde después (la semana de Navidad con poco consumo, sobre todo)
Las cuatro suman la distancia total. También lista las compras del agente y las del óptimo en esa semana.
"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))

import compra_banco_alineado as A  # noqa: E402
import p1_banco as B  # noqa: E402
from battery.optimizer import plan, score_weights  # noqa: E402
from battery.sim import baseline_totals, simulate  # noqa: E402

Z0 = B.NOV * B.WEEK      # primera hora de la semana de noviembre


def tail_cost(df, w, t0: int, soc0: float, wc: float, wk: float) -> float:
    """Coste (en puntos de score) del óptimo desde la hora t0 con la carga soc0."""
    d = df.iloc[t0:]
    a = plan(soc0, d.load_kw.to_numpy(), d.pv_kw.to_numpy(), d.price_eur_kwh.to_numpy(), d.co2_kg_kwh.to_numpy(), wc, wk, 0.0)
    return float((np.maximum(d.load_kw.to_numpy() - d.pv_kw.to_numpy() + a, 0.0) * w[t0:]).sum())


def one(job):
    ep_id, seed, spec, aligned = job
    if aligned:
        A.align_sources()
    df = B.make_episode(seed, "nov0")
    base = baseline_totals(df)
    wc, wk = score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df))
    w = 100 * (0.7 * df.co2_kg_kwh / base["co2_kg"] + 0.3 * df.price_eur_kwh / base["cost_eur"]).to_numpy()
    wn = w / w.mean()
    opt = simulate(B._oracle(df), df).log
    log = simulate(B.load_factory(spec)(), df).log
    imp, soc = log.import_kw.to_numpy(), log.soc_kwh.to_numpy()
    total = float((imp * w).sum())
    best = float((opt.import_kw.to_numpy() * w).sum())
    at_start = float((imp[:Z0] * w[:Z0]).sum()) + tail_cost(df, w, Z0, soc[Z0 - 1], wc, wk)
    at_hour1 = float((imp[:Z0 + 1] * w[:Z0 + 1]).sum()) + tail_cost(df, w, Z0 + 1, soc[Z0], wc, wk)
    at_end = float((imp[:Z0 + 168] * w[:Z0 + 168]).sum()) + tail_cost(df, w, Z0 + 168, soc[Z0 + 167], wc, wk)

    def buys(actions):
        return " ".join(f"d{(t - Z0) // 24 + 1}h{t % 24:02d}:{actions[t]:+.0f}@{wn[t]:.2f}"
                        for t in range(Z0, Z0 + 168) if abs(actions[t]) > 1)

    valleys = np.sort(wn[Z0:Z0 + 168].reshape(7, 24), axis=1)[:, :4].mean(axis=1)
    return {"id": ep_id, "total": total - best, "llegada": at_start - best, "hora 1": at_hour1 - at_start,
            "compra": at_end - at_hour1, "resto": total - at_end, "carga al llegar": soc[Z0 - 1], "carga al salir": soc[Z0 + 167],
            "valles": np.round(valleys, 2), "agente": buys(log.action_kw.to_numpy()), "óptimo": buys(opt.action_kw.to_numpy())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", default="actual")
    ap.add_argument("--banco", default="alineado", choices=["alineado", "estandar"])
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    eps = [e for e in B.suite("dev") if e[2] == "nov0"]
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        rows = list(ex.map(one, [(i, s, args.agent, args.banco == "alineado") for i, s, _ in eps]))
    t = pd.DataFrame(rows).set_index("id")
    pd.set_option("display.width", 200)
    cols = ["total", "llegada", "hora 1", "compra", "resto"]
    print(f"banco {args.banco}, agente {args.agent}: pérdida frente al óptimo en nov0 (puntos de score)")
    print(t[cols + ["carga al llegar", "carga al salir"]].round(4).to_string())
    print("media      " + "  ".join(f"{c} {t[c].mean():.4f}" for c in cols))
    print("\ncompras en la semana sin datos (día, hora, kW y peso de la hora; 1,00 = hora media del episodio)")
    for ep_id, r in t.iterrows():
        print(f"{ep_id} valles por día {r['valles']}\n   agente: {r['agente']}\n   óptimo: {r['óptimo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
