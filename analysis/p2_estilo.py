"""Estilo común de las gráficas de P2 (pensadas para una slide). Owner: P2."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
FIGS = REPO / "analysis" / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

AZUL, NARANJA, VERDE, GRIS = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"   # CO2, precio, tercera serie, contexto
TINTA, TINTA2, REJILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "font.size": 12, "axes.titlesize": 14, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA2, "text.color": TINTA,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.grid": True, "grid.color": REJILLA,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "axes.axisbelow": True, "lines.linewidth": 2, "legend.frameon": False, "figure.dpi": 100,
})


def guardar(fig, nombre: str) -> Path:
    out = FIGS / nombre
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("figura:", out.relative_to(REPO))
    return out
