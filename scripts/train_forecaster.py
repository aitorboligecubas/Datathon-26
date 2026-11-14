"""Genera los artefactos que el agente lee de models/ (y que van dentro del ZIP).

Owner: P2 (datos y análisis).

    python scripts/train_forecaster.py

Salidas (solo con el split de TRAIN, nunca con la validación):
    models/forecaster.json      perfil de demanda por hora de la semana (168) y solar por hora (24)
    models/objective_refs.json  media horaria de CO2 (kg) y coste (€) sin batería -> pesos del LP

Si pasáis a modelos .pkl (sklearn/lightgbm con joblib), guardadlos también en
models/ y cargadlos en forecaster.py; build_submission.py los mete en el ZIP.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from battery.data import is_synthetic, load, train_split  # noqa: E402
from battery.sim import baseline_totals  # noqa: E402


def main() -> None:
    if is_synthetic():
        print("OJO: no hay data/processed/hourly.csv; entreno con datos SINTÉTICOS.")
    train = train_split(load())
    how = train.timestamp.dt.weekday * 24 + train.timestamp.dt.hour
    prior = {
        "load_how": train.groupby(how)["load_kw"].mean().reindex(range(168)).round(3).tolist(),
        "pv_hod": train.groupby(train.timestamp.dt.hour)["pv_kw"].mean().reindex(range(24)).round(3).tolist(),
    }
    base = baseline_totals(train)
    refs = {"co2_ref_kg_per_h": base["co2_kg"] / len(train), "cost_ref_eur_per_h": base["cost_eur"] / len(train)}

    out = REPO / "models"
    out.mkdir(exist_ok=True)
    (out / "forecaster.json").write_text(json.dumps(prior))
    (out / "objective_refs.json").write_text(json.dumps(refs, indent=2))
    print(f"models/forecaster.json y models/objective_refs.json escritos ({len(train)} h de train)")
    print(f"refs: {refs}")


if __name__ == "__main__":
    main()
