"""Carga de datos al formato estándar del equipo. NO se empaqueta.

Owner: P2 (datos y análisis).

Formato estándar (lo usan simulador, previsión, eval y análisis):
    timestamp       datetime, una fila por hora, ordenado
    load_kw         demanda del campus en la hora
    pv_kw           producción solar en la hora
    price_eur_kwh   precio PVPC en €/kWh
    co2_kg_kwh       intensidad de CO2 del mix en kg CO2/kWh

Datos oficiales: el ZIP del reto está en el repo (oficial.zip) y se descomprime solo en oficial/
(ensure_official; funciona en Mac, Windows y en la nube). `build_hourly` reproduce el preprocesado de oficial/starter_kit/tutorial.ipynb
(demanda = -contador, solar = suma de los 3 inversores, medias horarias) y lo guarda
en data/processed/hourly.csv. Si no hay datos oficiales, se usan sintéticos.

Split (imita el test oficial = última semana de cada mes):
    validación = últimas 168 h de cada mes del train
    train      = el resto
"""
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_DIR = REPO_ROOT / "oficial"
OFFICIAL_ZIP = REPO_ROOT / "oficial.zip"
ZIP_ROOT = "paquet_participants_datathon_upc/"
TRAIN_DIR = OFFICIAL_DIR / "data" / "train"
HOURLY_FILE = REPO_ROOT / "data" / "processed" / "hourly.csv"
SYNTHETIC_FILE = REPO_ROOT / "data" / "synthetic" / "campus_synthetic.csv"

STD_COLUMNS = ["timestamp", "load_kw", "pv_kw", "price_eur_kwh", "co2_kg_kwh"]
VAL_HOURS_PER_MONTH = 168


def ensure_official(force: bool = False) -> bool:
    """Descomprime oficial.zip en oficial/ si hace falta. Devuelve True si oficial/ está listo."""
    if (TRAIN_DIR / "contador.csv").exists() and not force:
        return True
    if not OFFICIAL_ZIP.exists():
        return False
    tmp = OFFICIAL_DIR.with_name("oficial_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(OFFICIAL_ZIP) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith("__MACOSX/") or "/._" in name or info.is_dir():
                continue
            rel = name[len(ZIP_ROOT):] if name.startswith(ZIP_ROOT) else name
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    shutil.rmtree(OFFICIAL_DIR, ignore_errors=True)
    tmp.rename(OFFICIAL_DIR)
    return (TRAIN_DIR / "contador.csv").exists()


def build_hourly(train_dir: Path = TRAIN_DIR) -> pd.DataFrame:
    """Tabla horaria a partir de los CSV oficiales (igual que tutorial.ipynb). Mejorable por P2:
    filtrado de anomalías, imputación de huecos, cambios de hora..."""
    cont = pd.read_csv(train_dir / "contador.csv", parse_dates=["Fecha"]).set_index("Fecha")
    load = (-cont["Contador - POTENCIA ACTIVA EXPORTADA (kW)"]).clip(lower=0, upper=5000)
    inv = pd.read_csv(train_dir / "inversor.csv", parse_dates=["Fecha"]).set_index("Fecha")
    # Una columna por inversor; cada uno satura a ~50 kW en los datos (las slides hablan de 450 kW).
    cols = [f"Inversor {i} - POTENCIA ACTIVA (kW)" for i in (1, 2, 3)]
    pv = inv[cols].fillna(0).sum(axis=1).clip(lower=0)
    price = pd.read_csv(train_dir / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co2 = pd.read_csv(train_dir / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    df = pd.DataFrame({
        "load_kw": load.resample("1h").mean(),
        "pv_kw": pv.resample("1h").mean(),
        "price_eur_kwh": price["precio_eur_per_kwh"],
        "co2_kg_kwh": co2["co2_kg_per_kwh"],
    }).dropna()
    df.index.name = "timestamp"
    return df.reset_index()[STD_COLUMNS]


def default_path() -> Path:
    if HOURLY_FILE.exists():
        return HOURLY_FILE
    if ensure_official():
        HOURLY_FILE.parent.mkdir(parents=True, exist_ok=True)
        build_hourly().to_csv(HOURLY_FILE, index=False)
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
    """Últimas 168 h de cada mes (solo meses con al menos 2 semanas de datos)."""
    month = df["timestamp"].dt.to_period("M")
    rank_from_end = df.groupby(month).cumcount(ascending=False)
    month_size = df.groupby(month)["timestamp"].transform("size")
    return (rank_from_end < VAL_HOURS_PER_MONTH) & (month_size >= 2 * VAL_HOURS_PER_MONTH)


def validation_split(df: pd.DataFrame) -> pd.DataFrame:
    """Las 12 semanas de validación seguidas, como un único episodio (igual que el test)."""
    return df[validation_mask(df)].reset_index(drop=True)


def train_split(df: pd.DataFrame) -> pd.DataFrame:
    return df[~validation_mask(df)].reset_index(drop=True)
