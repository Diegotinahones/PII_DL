from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import pandas as pd


@dataclass(frozen=True)
class ColumnMap:
    time_col: str
    value_col: str
    geo_col: Optional[str]
    freq_col: Optional[str]
    unit_col: Optional[str]


def _read_raw_csv(path: Path) -> pd.DataFrame:
    # Cargar CSV como texto para preservar códigos SDMX (evitar casts agresivos)
    print("Cargando CSV bruto...")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    print(f"CSV cargado correctamente. Filas: {len(df)}, Columnas: {df.shape[1]}")
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Normalizar nombres de columnas (minúsculas + strip) para detección robusta
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _detect_time_column(cols: List[str]) -> str:
    # Detectar columna temporal típica SDMX-CSV
    candidates = ["time_period", "time", "year", "periode", "period"]
    for c in candidates:
        if c in cols:
            return c
    raise RuntimeError("No se ha detectado columna temporal (esperada: TIME_PERIOD o similar).")


def _coerce_numeric_series(s: pd.Series) -> pd.Series:
    # Convertir a numérico manejando ':' y comas
    cleaned = s.astype(str).str.strip()
    cleaned = cleaned.replace({":": pd.NA, "": pd.NA, "nan": pd.NA, "NaN": pd.NA})
    cleaned = cleaned.str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def _detect_value_column(df: pd.DataFrame) -> str:
    # Detectar columna de valor (preferir obs_value; si no, buscar la más numérica)
    cols = list(df.columns)
    if "obs_value" in cols:
        return "obs_value"

    best_col: Optional[str] = None
    best_non_null = -1

    for c in cols:
        if c in {"time_period", "time", "year"}:
            continue
        numeric = _coerce_numeric_series(df[c])
        non_null = int(numeric.notna().sum())
        if non_null > best_non_null:
            best_non_null = non_null
            best_col = c

    if not best_col or best_non_null <= 0:
        raise RuntimeError("No se ha podido detectar una columna numérica de valores.")
    return best_col


def _detect_optional_column(cols: List[str], candidates: List[str]) -> Optional[str]:
    # Detectar columna opcional por lista de candidatos
    for c in candidates:
        if c in cols:
            return c
    return None


def _extract_year(series: pd.Series) -> pd.Series:
    # Extraer año de TIME_PERIOD (manejar '2023' o '2023-01' u otros formatos)
    s = series.astype(str).str.strip()
    year = s.str.extract(r"(\d{4})", expand=False)
    return pd.to_numeric(year, errors="coerce").astype("Int64")


def _filter_if_present(df: pd.DataFrame, col: Optional[str], allowed: List[str]) -> Tuple[pd.DataFrame, str]:
    # Filtrar si existe columna y devolver mensaje
    if not col:
        return df, "Filtro no aplicado (columna no presente)."
    before = len(df)
    df2 = df[df[col].isin(allowed)].copy()
    after = len(df2)
    return df2, f"Filtro aplicado en '{col}': {before} → {after} (permitidos: {allowed})"


def _write_report(report_path: Path, lines: List[str]) -> None:
    # Escribir informe de limpieza
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    raw_path = Path("data/raw/eurostat_ai.csv")
    out_path = Path("data/processed/ai_clean.csv")
    report_path = Path("outputs/clean_report.txt")

    print("Iniciando limpieza del dataset...")
    if not raw_path.exists():
        raise RuntimeError(f"No se encuentra el fichero: {raw_path} (ejecutar antes DownloadData.py)")

    df_raw = _read_raw_csv(raw_path)
    df = _normalize_columns(df_raw)

    print("Detectando columnas clave...")
    cols = list(df.columns)
    time_col = _detect_time_column(cols)
    value_col = _detect_value_column(df)

    geo_col = _detect_optional_column(cols, ["geo", "country", "ref_area"])
    freq_col = _detect_optional_column(cols, ["freq", "frequency"])
    unit_col = _detect_optional_column(cols, ["unit", "unit_measure"])

    cmap = ColumnMap(
        time_col=time_col,
        value_col=value_col,
        geo_col=geo_col,
        freq_col=freq_col,
        unit_col=unit_col,
    )

    print(f"Columna temporal detectada: {cmap.time_col}")
    print(f"Columna de valor detectada: {cmap.value_col}")
    print(f"Columna geográfica: {cmap.geo_col if cmap.geo_col else '(no detectada)'}")
    print(f"Columna de frecuencia: {cmap.freq_col if cmap.freq_col else '(no detectada)'}")
    print(f"Columna de unidad: {cmap.unit_col if cmap.unit_col else '(no detectada)'}")

    report_lines: List[str] = []
    report_lines.append("INFORME DE LIMPIEZA (CleanData.py)")
    report_lines.append(f"Archivo de entrada: {raw_path.as_posix()}")
    report_lines.append(f"Filas/columnas iniciales: {len(df)} / {df.shape[1]}")
    report_lines.append(f"Columna temporal: {cmap.time_col}")
    report_lines.append(f"Columna de valor: {cmap.value_col}")
    report_lines.append(f"Columna geo: {cmap.geo_col}")
    report_lines.append(f"Columna freq: {cmap.freq_col}")
    report_lines.append(f"Columna unit: {cmap.unit_col}")
    report_lines.append("")

    # Filtrar frecuencia anual si existe
    if cmap.freq_col:
        df, msg = _filter_if_present(df, cmap.freq_col, ["A"])
        print(msg)
        report_lines.append(msg)

    # Intentar fijar unidad a porcentaje si existe (PC o PCT suelen ser habituales)
    if cmap.unit_col:
        unique_units = sorted([u for u in df[cmap.unit_col].dropna().unique().tolist() if str(u).strip() != ""])
        report_lines.append(f"Unidades detectadas (previo a filtro): {unique_units[:30]}{' ...' if len(unique_units) > 30 else ''}")

        preferred = None
        for candidate in ["PC", "PCT", "PC_ENT", "PC_TOTAL"]:
            if candidate in unique_units:
                preferred = candidate
                break

        if preferred:
            before = len(df)
            df = df[df[cmap.unit_col] == preferred].copy()
            after = len(df)
            msg = f"Filtro aplicado en '{cmap.unit_col}' para unidad porcentaje: {before} → {after} (unidad: {preferred})"
            print(msg)
            report_lines.append(msg)
        else:
            msg = "Filtro de unidad no aplicado (no se ha encontrado una unidad porcentaje estándar)."
            print(msg)
            report_lines.append(msg)

    # Limpiar y convertir tiempo/valor
    print("Normalizando año y valores numéricos...")
    df["year"] = _extract_year(df[cmap.time_col])
    df["value"] = _coerce_numeric_series(df[cmap.value_col])

    # Eliminar filas sin año o sin valor
    before_drop = len(df)
    df = df[df["year"].notna() & df["value"].notna()].copy()
    after_drop = len(df)
    msg = f"Eliminación de filas sin año o sin valor: {before_drop} → {after_drop}"
    print(msg)
    report_lines.append(msg)

    # Reordenar columnas (mantener dimensiones originales + year/value al final)
    keep_dims = [c for c in df.columns if c not in {"year", "value"}]
    ordered_cols = keep_dims + ["year", "value"]
    df = df[ordered_cols]

    # Guardar dataset limpio
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Dataset limpio guardado correctamente en: {out_path.resolve()}")

    # Resumen rápido para control de calidad
    report_lines.append("")
    report_lines.append(f"Filas finales: {len(df)}")
    report_lines.append(f"Años disponibles (min/max): {int(df['year'].min())} / {int(df['year'].max())}")

    if cmap.geo_col and cmap.geo_col in df.columns:
        n_geo = int(df[cmap.geo_col].nunique(dropna=True))
        report_lines.append(f"Geografías distintas (según '{cmap.geo_col}'): {n_geo}")

    report_lines.append("Columnas finales:")
    report_lines.append(", ".join(df.columns))

    _write_report(report_path, report_lines)
    print(f"Informe de limpieza guardado en: {report_path.resolve()}")
    print("Limpieza completada correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
