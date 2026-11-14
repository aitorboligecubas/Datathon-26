"""Descomprime el paquete oficial del reto (oficial.zip) en oficial/.

Owner: integrador.

    python scripts/preparar_oficial.py          # funciona igual en Mac, Windows y en la nube (Linux)
    python scripts/preparar_oficial.py --force  # vuelve a descomprimir aunque ya exista oficial/

El ZIP oficial está en el repo (oficial.zip). Dentro trae una carpeta
`paquet_participants_datathon_upc/` y basura de macOS (`__MACOSX/`): este script quita las dos
cosas y deja oficial/docs, oficial/starter_kit y oficial/data/train. oficial/ está en .gitignore
(es solo la copia descomprimida).

No hace falta llamarlo a mano: battery.data, eval.py, calibrate_sim.py y build_submission.py
lo hacen solos si falta oficial/.
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from battery.data import OFFICIAL_DIR, OFFICIAL_ZIP, ensure_official  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="volver a descomprimir aunque ya exista oficial/")
    args = ap.parse_args()
    if not OFFICIAL_ZIP.exists():
        print(f"No encuentro {OFFICIAL_ZIP.name} en la raíz del repo.", file=sys.stderr)
        return 1
    if ensure_official(force=args.force):
        n = sum(1 for _ in OFFICIAL_DIR.rglob("*") if _.is_file())
        print(f"oficial/ listo ({n} ficheros): docs/, starter_kit/ y data/train/")
        return 0
    print("No se ha podido preparar oficial/.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
