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
import os
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
VARIANTS = ("oficial", "limpio", "real")


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


P_COL = "Contador - POTENCIA ACTIVA EXPORTADA (kW)"
E_COL = "Contador - ENERGIA ACTIVA IMPORTADA (kWh)"
READ_COL = "Contador - FECHA ULTIMA LECTURA"
COM_COL = "Contador - ESTADO COM"
PV_COLS = [f"Inversor {i} - POTENCIA ACTIVA (kW)" for i in (1, 2, 3)]
NIGHT_HOURS = 8.0   # el contador no se lee de 22:10 a 06:00; a las 06:05 llega la energía de esas 8 h


def read_meter(train_dir: Path = TRAIN_DIR) -> pd.DataFrame:
    """Contador a 5 min con banderas de calidad (ver analysis/calidad_datos.md).

    Columnas: load_kw (como el tutorial: -potencia, recortada a 0..5000), com_fail (ESTADO COM = 255:
    fallo de comunicación, la potencia vale 0), frozen (el contador no se ha vuelto a leer: la potencia
    repite el último valor) y night_real_kw (consumo medio real del bloque congelado, calculado con la
    energía acumulada que llega en la primera lectura posterior; NaN si no se puede calcular).
    """
    c = pd.read_csv(train_dir / "contador.csv", parse_dates=["Fecha"],
                    usecols=["Fecha", P_COL, E_COL, READ_COL, COM_COL]).sort_values("Fecha")
    c = c.reset_index(drop=True)
    c["load_kw"] = (-c[P_COL]).clip(lower=0, upper=5000)
    c["com_fail"] = (c[COM_COL] != 0) | c[P_COL].isna()
    c["frozen"] = (c[READ_COL].diff() == 0) & ~c["com_fail"]
    block = (c["frozen"] != c["frozen"].shift()).cumsum()
    c["night_real_kw"] = float("nan")
    for _, g in c[c["frozen"]].groupby(block):
        nxt = g.index[-1] + 1
        if len(g) < 12 or nxt not in c.index:
            continue
        energy = c.at[nxt, E_COL]
        if c.at[nxt, "Fecha"] - g["Fecha"].iloc[-1] == pd.Timedelta("5min") and 3000 < energy < 12000:
            c.loc[g.index, "night_real_kw"] = energy / NIGHT_HOURS
    return c[["Fecha", "load_kw", "com_fail", "frozen", "night_real_kw"]]


def _profile_fill(s: pd.Series, by_weekday: bool) -> pd.Series:
    """Rellena NaN: interpolación lineal en huecos de hasta 2 h y, si no, la media del mismo mes y hora
    (y tipo de día, si by_weekday) de los datos válidos; último recurso, la media de esa hora."""
    out = s.interpolate(limit=2, limit_area="inside")
    idx = out.index
    daytype = idx.dayofweek.where(idx.dayofweek >= 5, 0) if by_weekday else idx.dayofweek * 0
    keys = [idx.to_period("M"), daytype, idx.hour]
    out = out.fillna(out.groupby(keys).transform("mean"))
    return out.fillna(out.groupby(idx.hour).transform("mean"))


def build_hourly(train_dir: Path = TRAIN_DIR, variant: str = "oficial") -> pd.DataFrame:
    """Tabla horaria a partir de los CSV oficiales.

    variant="oficial" (por defecto): igual que tutorial.ipynb (demanda = -contador, solar = suma de los
        3 inversores, medias horarias, dropna). Es la que usa el equipo para validar: imita el test.
    variant="limpio": corrige lo que es claramente un fallo de medida, sin tocar lo demás:
        - fallos de comunicación (ESTADO COM = 255; el contador y los inversores marcan 0) -> se imputan;
        - horas sin registros dentro de un día con datos -> se imputan;
        - días con contador pero sin inversores (17-24 de agosto) -> solar del perfil del mes, en vez de
          tirar la semana entera.
    variant="real": "limpio" + el consumo nocturno REAL. El contador no se lee de 22:10 a 06:00 y la
        potencia repite el último valor; aquí se sustituye por la energía realmente consumida esa noche
        (repartida uniforme). Sirve para el análisis: el test oficial lleva el valor congelado.
    """
    price = pd.read_csv(train_dir / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co2 = pd.read_csv(train_dir / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    inv = pd.read_csv(train_dir / "inversor.csv", parse_dates=["Fecha"],
                      usecols=["Fecha"] + PV_COLS).set_index("Fecha")
    if variant == "oficial":
        cont = pd.read_csv(train_dir / "contador.csv", parse_dates=["Fecha"]).set_index("Fecha")
        load = (-cont[P_COL]).clip(lower=0, upper=5000)
        # Una columna por inversor; cada uno satura a ~50 kW en los datos (las slides hablan de 450 kW).
        pv = inv[PV_COLS].fillna(0).sum(axis=1).clip(lower=0)
        df = pd.DataFrame({
            "load_kw": load.resample("1h").mean(),
            "pv_kw": pv.resample("1h").mean(),
            "price_eur_kwh": price["precio_eur_per_kwh"],
            "co2_kg_kwh": co2["co2_kg_per_kwh"],
        }).dropna()
    elif variant in ("limpio", "real"):
        m = read_meter(train_dir).set_index("Fecha")
        load5 = m["load_kw"].mask(m["com_fail"])
        if variant == "real":
            load5 = load5.mask(m["frozen"] & m["night_real_kw"].notna(), m["night_real_kw"])
        fail5 = m["com_fail"].reindex(inv.index, fill_value=False)
        pv5 = inv[PV_COLS].sum(axis=1, min_count=1).clip(lower=0).mask(fail5)
        load_h = load5.resample("1h").mean()
        if variant == "real":
            # Última noche de cada bloque (sin lectura posterior): la media real de las noches del mes.
            fr = (m["frozen"] & m["night_real_kw"].isna()).resample("1h").mean() > 0.5
            night = m["night_real_kw"].resample("1h").mean()
            month_night = night.groupby(night.index.to_period("M")).transform("mean")
            load_h = load_h.mask(fr.reindex(load_h.index, fill_value=False), month_night)
        # Horas válidas: con precio y CO2, en días en los que el contador tiene datos.
        days_ok = pd.Index(m.index[~m["com_fail"]].normalize().unique())
        hours = price.index.intersection(co2.index)
        hours = hours[hours.normalize().isin(days_ok)]
        hours = hours[(hours >= m.index.min().floor("h")) & (hours <= m.index.max())]
        # Un día suelto (1 registro a las 00:00 del día 1 del mes siguiente) no es un día con datos.
        per_day = m["load_kw"].groupby(m.index.normalize()).size()
        hours = hours[hours.normalize().isin(per_day[per_day >= 144].index)]
        df = pd.DataFrame({
            "load_kw": _profile_fill(load_h.reindex(hours), by_weekday=True),
            "pv_kw": _profile_fill(pv5.resample("1h").mean().reindex(hours), by_weekday=False),
            "price_eur_kwh": price["precio_eur_per_kwh"].reindex(hours),
            "co2_kg_kwh": co2["co2_kg_per_kwh"].reindex(hours),
        }).dropna()
    else:
        raise ValueError(f"variante desconocida: {variant}")
    df.index.name = "timestamp"
    return df.reset_index()[STD_COLUMNS]


def data_variant() -> str:
    """Variante de datos activa: variable de entorno BATTERY_DATOS = oficial (por defecto) | limpio | real.

        BATTERY_DATOS=limpio python eval.py --agent all --log "datos limpios"
    """
    v = os.environ.get("BATTERY_DATOS", "oficial").strip().lower()
    if v not in VARIANTS:
        raise ValueError(f"BATTERY_DATOS={v!r}: tiene que ser una de {VARIANTS}")
    return v


def hourly_file(variant: str = "oficial") -> Path:
    return HOURLY_FILE if variant == "oficial" else HOURLY_FILE.with_name(f"hourly_{variant}.csv")


def default_path() -> Path:
    variant = data_variant()
    path = hourly_file(variant)
    if path.exists():
        return path
    if ensure_official():
        path.parent.mkdir(parents=True, exist_ok=True)
        build_hourly(variant=variant).to_csv(path, index=False)
        return path
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
