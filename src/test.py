from __future__ import annotations

from pathlib import Path
from typing import Final, Tuple
import sys
import urllib.request

import pandas as pd
import plotly.express as px


CSV_URL: Final[str] = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"


def _ensure_dirs(project_root: Path) -> Tuple[Path, Path]:
    """Crear carpetas de trabajo si no existen."""
    data_raw_dir = project_root / "data" / "raw"
    outputs_dir = project_root / "outputs"
    data_raw_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return data_raw_dir, outputs_dir


def _download_csv(url: str, dest_path: Path) -> None:
    """Descargar un CSV desde una URL."""
    # Evitar re-descargas innecesarias si ya existe
    if dest_path.exists() and dest_path.stat().st_size > 0:
        print(f"CSV ya existe en: {dest_path}")
        return

    print("Descargando CSV...")
    try:
        # Definir timeout para evitar bloqueos
        with urllib.request.urlopen(url, timeout=20) as response:
            content = response.read()
        dest_path.write_bytes(content)
    except Exception as exc:
        raise RuntimeError(f"No se pudo descargar el CSV desde {url}. Error: {exc}") from exc

    if not dest_path.exists() or dest_path.stat().st_size == 0:
        raise RuntimeError("Descarga finalizada, pero el fichero está vacío o no existe.")

    print("CSV descargado correctamente.")


def _fallback_generate_csv(dest_path: Path) -> None:
    """Generar un CSV local de respaldo si no hay internet."""
    print("Generando CSV local de respaldo (sin internet)...")
    df = pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5],
            "y": [1, 4, 9, 16, 25],
            "grupo": ["A", "A", "B", "B", "B"],
        }
    )
    dest_path.write_text(df.to_csv(index=False), encoding="utf-8")
    print("CSV local generado correctamente.")


def _load_dataframe(csv_path: Path) -> pd.DataFrame:
    """Cargar el CSV en un DataFrame y validar contenido mínimo."""
    print("Cargando CSV en pandas...")
    df = pd.read_csv(csv_path)

    if df.empty:
        raise RuntimeError("El DataFrame está vacío.")
    if df.shape[1] < 2:
        raise RuntimeError("El DataFrame no tiene suficientes columnas para un gráfico de prueba.")

    print(f"CSV cargado correctamente. Filas: {df.shape[0]}, Columnas: {df.shape[1]}")
    print("Columnas detectadas:", ", ".join(df.columns.astype(str).tolist()))
    return df


def _generate_plot(df: pd.DataFrame, outputs_dir: Path) -> Path:
    """Generar un gráfico Plotly y exportarlo a HTML."""
    print("Generando gráfico de prueba...")

    # Elegir un gráfico según columnas disponibles (iris o fallback)
    if {"sepal_length", "sepal_width", "species"}.issubset(set(df.columns)):
        fig = px.scatter(
            df,
            x="sepal_length",
            y="sepal_width",
            color="species",
            title="Test Plotly: Iris (sepal_length vs sepal_width)",
        )
    elif {"x", "y", "grupo"}.issubset(set(df.columns)):
        fig = px.line(df, x="x", y="y", color="grupo", markers=True, title="Test Plotly: CSV local de respaldo")
    else:
        # Si el CSV fuese distinto, intentar usar las dos primeras columnas numéricas
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if len(numeric_cols) < 2:
            raise RuntimeError("No hay al menos 2 columnas numéricas para generar el gráfico.")
        fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title="Test Plotly: columnas numéricas detectadas")

    out_html = outputs_dir / "test_plotly.html"
    # Usar CDN para que el archivo sea ligero (requiere internet al abrir el HTML)
    fig.write_html(str(out_html), include_plotlyjs="cdn", full_html=True)

    print(f"Gráfico generado y guardado en: {out_html}")
    return out_html


def main() -> int:
    """Ejecutar test de entorno completo."""
    print("Iniciando test de entorno (Python + pandas + Plotly)...")

    project_root = Path(__file__).resolve().parent
    data_raw_dir, outputs_dir = _ensure_dirs(project_root)
    csv_path = data_raw_dir / "iris.csv"

    try:
        _download_csv(CSV_URL, csv_path)
    except Exception as exc:
        print(f"Aviso: fallo al descargar CSV. Motivo: {exc}")
        _fallback_generate_csv(csv_path)

    df = _load_dataframe(csv_path)
    _generate_plot(df, outputs_dir)

    print("Test de comprobación completado correctamente.")
    print("Abrir el HTML generado en el navegador para validar el resultado.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
