"""Carga de datos al formato estándar del equipo. NO se empaqueta.

Owner: P2 (previsión).

Formato estándar (lo usan simulador, previsión, eval y análisis):
    timestamp       datetime, una fila por hora, ordenado
    load_kw         demanda del campus en la hora
    pv_kw           producción solar en la hora
    price_eur_kwh   precio PVPC en €/kWh
    co2_kg_kwh       intensidad de CO2 del mix en kg CO2/kWh

Datos oficiales: starter_kit/ (ZIP oficial descomprimido, no se sube: el repo es
público). Ficheros: contador.csv (15 min, demanda = -contador), inversor.csv
(5 min, 3 inversores), meteo.csv, entradas_salidas.csv, precio_pvpc.csv (1 h),
co2_red.csv (1 h). `build_hourly` los junta en data/processed/hourly.csv.
Mientras no exista, se usan datos sintéticos para que todo funcione igual.

Split (imita el test oficial = última semana de cada mes):
    validación = últimas 168 h de cada mes del train
    train      = el resto
"""
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_DIR = REPO_ROOT / "starter_kit"
HOURLY_FILE = REPO_ROOT / "data" / "processed" / "hourly.csv"
SYNTHETIC_FILE = REPO_ROOT / "data" / "synthetic" / "campus_synthetic.csv"

STD_COLUMNS = ["timestamp", "load_kw", "pv_kw", "price_eur_kwh", "co2_kg_kwh"]
VAL_HOURS_PER_MONTH = 168


def build_hourly(starter_dir: Path = STARTER_DIR) -> pd.DataFrame:
    """TODO P2: leer los CSV oficiales, pasar todo a horario y devolver STD_COLUMNS.

    Pistas: contador a 15 min -> media horaria, demanda = -contador (VERIFICAR con
    tutorial.ipynb); inversor a 5 min, sumar los 3 inversores; precio a €/kWh.
    Guardar el resultado con `df.to_csv(HOURLY_FILE, index=False)`.
    """
    raise NotImplementedError("P2: implementar build_hourly a partir de starter_kit/")


def default_path() -> Path:
    if HOURLY_FILE.exists():
        return HOURLY_FILE
    if not SYNTHETIC_FILE.exists():
        from .synthetic import make_synthetic
        SYNTHETIC_FILE.parent.mkdir(parents=True, exist_ok=True)
        make_synthetic().to_csv(SYNTHETIC_FILE, index=False)
    return SYNTHETIC_FILE


def is_synthetic(path: Optional[Path] = None) -> bool:
    return Path(path or default_path()) == SYNTHETIC_FILE


def load(path: Optional[Path] = None) -> pd.DataFrame:
    df = pd.read_csv(path or default_path(), parse_dates=["timestamp"])
    df = df[STD_COLUMNS].sort_values("timestamp").reset_index(drop=True)
    num = STD_COLUMNS[1:]
    df[num] = df[num].interpolate(limit_direction="both")
    return df


def validation_mask(df: pd.DataFrame) -> pd.Series:
    month = df["timestamp"].dt.to_period("M")
    rank_from_end = df.groupby(month).cumcount(ascending=False)
    return rank_from_end < VAL_HOURS_PER_MONTH


def validation_split(df: pd.DataFrame) -> pd.DataFrame:
    """Las 12 semanas de validación seguidas, como un único episodio (igual que el test)."""
    return df[validation_mask(df)].reset_index(drop=True)


def train_split(df: pd.DataFrame) -> pd.DataFrame:
    return df[~validation_mask(df)].reset_index(drop=True)
