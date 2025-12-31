from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


OUT_DIR = Path("outputs")
CHARTS_DIR = OUT_DIR / "charts"

# Entradas generadas por BuildProjectTables.py
TOP15_PATH = OUT_DIR / "adoption_top15_last_year.csv"
SERIES_PATH = OUT_DIR / "adoption_country_year.csv"
RANK_PATH = OUT_DIR / "adoption_country_year_rank.csv"


@dataclass(frozen=True)
class FocusConfig:
    eu_code: str
    es_code: str
    focus_geos: List[str]


def _ensure_dirs() -> None:
    # Crear carpeta de salida de gráficos
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_csv(path: Path, name: str) -> pd.DataFrame:
    # Cargar CSV y validar existencia
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {name}: {path} (ejecutar antes BuildProjectTables.py)")
    print(f"Cargando {name}...")
    df = pd.read_csv(path, low_memory=False)
    print(f"{name} cargado correctamente. Filas: {len(df)}, Columnas: {df.shape[1]}")
    return df


def _detect_focus(series_df: pd.DataFrame) -> FocusConfig:
    # Detectar códigos de UE y España presentes en el dataset
    geos = set(series_df["geo"].astype(str).unique().tolist())
    eu = "EU27_2020" if "EU27_2020" in geos else ("EU27" if "EU27" in geos else "EU")
    es = "ES" if "ES" in geos else "ES"

    # Definir lista de países foco (mantener manejable)
    focus = [eu, es]
    for cand in ["DE", "FR", "IT", "PT", "NL"]:
        if cand in geos and cand not in focus:
            focus.append(cand)

    return FocusConfig(eu_code=eu, es_code=es, focus_geos=focus)


def _format_geo_label(geo: str, eu_code: str, es_code: str) -> str:
    # Etiquetar de forma legible sin depender del color
    if geo == es_code:
        return "ES (España)"
    if geo == eu_code:
        return f"{eu_code} (UE-27)"
    return geo


def _save_plotly_html(fig: go.Figure, out_path: Path) -> None:
    # Exportar gráfico a HTML (ligero con CDN)
    fig.write_html(str(out_path), include_plotlyjs="cdn", full_html=True)
    print(f"HTML guardado en: {out_path.resolve()}")


def build_view_1_top15(top15_df: pd.DataFrame, focus: FocusConfig) -> Path:
    # Construir Vista 1: Top 15 países (último año)
    print("Generando Vista 1 (Top 15 países, último año)...")

    df = top15_df.copy()
    df["geo_label"] = df["geo"].astype(str).apply(lambda g: _format_geo_label(g, focus.eu_code, focus.es_code))
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # Ordenar para barras horizontales (de mayor a menor)
    df = df.sort_values("value", ascending=True)

    fig = px.bar(
        df,
        x="value",
        y="geo_label",
        orientation="h",
        text="value",
        title=f"Adopción de IA (empresas que usan IA) — Top 15 países ({int(df['year'].max())})",
        labels={"value": "Porcentaje de empresas (%)", "geo_label": "País/área"},
    )

    # Mostrar valores en barra para no depender del hover
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
    fig.update_layout(
        xaxis_tickformat=".0f",
        margin=dict(l=40, r=40, t=80, b=40),
    )

    out_path = CHARTS_DIR / "vista1_top15_last_year.html"
    _save_plotly_html(fig, out_path)
    return out_path


def build_view_2_trend_focus(series_df: pd.DataFrame, focus: FocusConfig) -> Path:
    # Construir Vista 2: evolución 2021–2025 para países foco
    print("Generando Vista 2 (Evolución temporal países foco)...")

    df = series_df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[df["geo"].astype(str).isin(focus.focus_geos)].copy()

    df["geo_label"] = df["geo"].astype(str).apply(lambda g: _format_geo_label(g, focus.eu_code, focus.es_code))

    fig = px.line(
        df.sort_values(["geo_label", "year"]),
        x="year",
        y="value",
        color="geo_label",
        markers=True,
        title="Evolución de la adopción de IA (2021–2025) — UE-27 vs España y comparadores",
        labels={"value": "Porcentaje de empresas (%)", "year": "Año", "geo_label": "País/área"},
    )

    fig.update_layout(
        xaxis=dict(dtick=1),
        yaxis_tickformat=".0f",
        margin=dict(l=40, r=40, t=80, b=40),
        legend_title_text="País/área (clic para ocultar/mostrar)",
    )

    out_path = CHARTS_DIR / "vista2_trend_focus_2021_2025.html"
    _save_plotly_html(fig, out_path)

    # Guardar tabla base de esta vista para referencia/revisión
    table_out = CHARTS_DIR / "vista2_trend_focus_table.csv"
    df[["geo", "geo_label", "year", "value"]].to_csv(table_out, index=False, encoding="utf-8")
    print(f"Tabla de soporte guardada en: {table_out.resolve()}")

    return out_path


def build_view_3_bump_ranking(rank_df: pd.DataFrame, focus: FocusConfig) -> Path:
    # Construir Vista 3: bump chart de ranking anual
    print("Generando Vista 3 (Ranking anual / bump chart)...")

    df = rank_df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")

    # Reducir ruido: quedarse con foco (UE-27, ES y comparadores) y top 15 último año
    df["geo"] = df["geo"].astype(str)
    df["geo_label"] = df["geo"].apply(lambda g: _format_geo_label(g, focus.eu_code, focus.es_code))

    # Tomar top 15 del último año para que el bump sea legible
    last_year = int(df["year"].max())
    top_geos = (
        df[df["year"] == last_year]
        .sort_values("rank", ascending=True)
        .head(15)["geo"]
        .astype(str)
        .tolist()
    )

    keep_geos = set(top_geos) | set(focus.focus_geos)
    df = df[df["geo"].isin(keep_geos)].copy()

    fig = px.line(
        df.sort_values(["geo_label", "year"]),
        x="year",
        y="rank",
        color="geo_label",
        markers=True,
        title="Ranking anual de adopción de IA (menor rank = mejor posición)",
        labels={"rank": "Posición en el ranking", "year": "Año", "geo_label": "País/área"},
    )

    # Invertir eje Y para que rank 1 quede arriba
    fig.update_yaxes(autorange="reversed", dtick=1)
    fig.update_layout(
        xaxis=dict(dtick=1),
        margin=dict(l=40, r=40, t=80, b=40),
        legend_title_text="País/área (clic para ocultar/mostrar)",
    )

    out_path = CHARTS_DIR / "vista3_bump_ranking.html"
    _save_plotly_html(fig, out_path)
    return out_path


def main() -> int:
    print("Iniciando generación de visualizaciones (Plotly)...")
    _ensure_dirs()

    top15 = _load_csv(TOP15_PATH, "adoption_top15_last_year.csv")
    series = _load_csv(SERIES_PATH, "adoption_country_year.csv")
    rank = _load_csv(RANK_PATH, "adoption_country_year_rank.csv")

    focus = _detect_focus(series)
    print(f"Foco detectado: UE={focus.eu_code}, ES={focus.es_code}, países foco={focus.focus_geos}")

    build_view_1_top15(top15, focus)
    build_view_2_trend_focus(series, focus)
    build_view_3_bump_ranking(rank, focus)

    print("Generación de visualizaciones completada correctamente.")
    print("Archivos HTML en: outputs/charts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
