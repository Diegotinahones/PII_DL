from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


INPUT_PATH = Path("data/processed/ai_clean.csv")
OUTPUT_DIR = Path("outputs")
REPORT_PATH = OUTPUT_DIR / "profile_report.txt"

# Elegir dimensiones clave a perfilar
DIM_COLS = ["indic_is", "nace_r2", "size_emp", "geo", "year"]


@dataclass(frozen=True)
class ProfileResult:
    col: str
    n_rows: int
    n_missing: int
    n_unique: int
    out_csv: Optional[Path]


def _ensure_outputs() -> None:
    """Crear carpeta outputs si no existe."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_clean_data(path: Path) -> pd.DataFrame:
    """Cargar el dataset limpio y validar columnas mínimas."""
    print("Cargando dataset limpio...")
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra: {path} (ejecutar antes CleanData.py)")

    df = pd.read_csv(path, low_memory=False)

    print(f"Dataset cargado correctamente. Filas: {len(df)}, Columnas: {df.shape[1]}")
    missing_cols = [c for c in DIM_COLS if c not in df.columns]
    if missing_cols:
        raise RuntimeError(f"Faltan columnas esperadas en el dataset limpio: {missing_cols}")

    return df


def _write_line(lines: list[str], text: str = "") -> None:
    """Añadir una línea al informe."""
    lines.append(text)


def _profile_column(df: pd.DataFrame, col: str, top_n: int = 50) -> ProfileResult:
    """Perfilar una columna y guardar recuentos en CSV."""
    n_rows = len(df)
    s = df[col]

    # Calcular métricas básicas
    n_missing = int(s.isna().sum())
    n_unique = int(s.nunique(dropna=True))

    # Calcular recuentos por valor (top N)
    counts = (
        s.astype("string")
        .fillna("<NA>")
        .value_counts(dropna=False)
        .rename_axis(col)
        .reset_index(name="count")
    )

    out_csv = OUTPUT_DIR / f"profile_{col}_counts.csv"
    counts.to_csv(out_csv, index=False, encoding="utf-8")

    return ProfileResult(col=col, n_rows=n_rows, n_missing=n_missing, n_unique=n_unique, out_csv=out_csv)


def _build_report(df: pd.DataFrame, cols: Iterable[str]) -> str:
    """Construir el texto del informe de perfilado."""
    lines: list[str] = []
    _write_line(lines, "INFORME DE PERFILADO (ProfileData.py)")
    _write_line(lines, f"Archivo de entrada: {INPUT_PATH.as_posix()}")
    _write_line(lines, f"Filas totales: {len(df)}")
    _write_line(lines, f"Columnas totales: {df.shape[1]}")
    _write_line(lines)

    # Resumen rápido de cobertura temporal y geográfica
    years = sorted(pd.Series(df["year"]).dropna().unique().tolist())
    geos = sorted(pd.Series(df["geo"]).dropna().unique().tolist())
    _write_line(lines, f"Años disponibles: {years[0]} → {years[-1]} (n={len(years)})" if years else "Años disponibles: (sin datos)")
    _write_line(lines, f"Geografías disponibles: n={len(geos)}")
    _write_line(lines)

    # Perfilar dimensiones principales
    _write_line(lines, "Dimensiones perfiladas (resumen):")
    for col in cols:
        result = _profile_column(df, col=col, top_n=50)
        _write_line(lines, f"- {result.col}: únicos={result.n_unique}, nulos={result.n_missing} (csv: {result.out_csv.as_posix() if result.out_csv else 'N/A'})")
    _write_line(lines)

    # Añadir una lista compacta de valores únicos para las dimensiones más importantes
    for col in ["indic_is", "nace_r2", "size_emp"]:
        _write_line(lines, f"Valores únicos detectados en '{col}':")
        uniques = sorted(pd.Series(df[col]).dropna().astype(str).unique().tolist())
        if uniques:
            # Limitar longitud para que el informe sea legible
            preview = uniques[:200]
            _write_line(lines, ", ".join(preview) + (" ..." if len(uniques) > len(preview) else ""))
        else:
            _write_line(lines, "(sin valores)")
        _write_line(lines)

    return "\n".join(lines) + "\n"


def main() -> int:
    print("Iniciando perfilado de dimensiones...")
    _ensure_outputs()

    df = _load_clean_data(INPUT_PATH)

    print("Generando informe y recuentos por dimensión...")
    report_text = _build_report(df, DIM_COLS)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    print(f"Informe guardado correctamente en: {REPORT_PATH.resolve()}")
    print("Recuentos guardados en outputs/profile_*_counts.csv")
    print("Perfilado completado correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
