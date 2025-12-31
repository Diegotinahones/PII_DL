from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go


OUT_DIR = Path("outputs")
CHARTS_DIR = OUT_DIR / "charts"

TOP15_PATH = OUT_DIR / "adoption_top15_last_year.csv"
SERIES_PATH = OUT_DIR / "adoption_country_year.csv"
RANK_PATH = OUT_DIR / "adoption_country_year_rank.csv"


@dataclass(frozen=True)
class FocusConfig:
    eu_code: str
    es_code: str
    focus_geos: List[str]


def _ensure_dirs() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_csv(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {name}: {path} (ejecutar scripts previos)")
    print(f"Cargando {name}...")
    df = pd.read_csv(path, low_memory=False)
    print(f"{name} cargado correctamente. Filas: {len(df)}, Columnas: {df.shape[1]}")
    return df


def _detect_focus(series_df: pd.DataFrame) -> FocusConfig:
    geos = set(series_df["geo"].astype(str).unique().tolist())

    eu = "EU27_2020" if "EU27_2020" in geos else ("EU27" if "EU27" in geos else ("EU" if "EU" in geos else "EU27_2020"))
    es = "ES" if "ES" in geos else "ES"

    focus = [eu, es]
    for cand in ["DE", "FR", "IT", "PT", "NL"]:
        if cand in geos and cand not in focus:
            focus.append(cand)

    return FocusConfig(eu_code=eu, es_code=es, focus_geos=focus)


def _format_geo_label(geo: str, eu_code: str, es_code: str) -> str:
    if geo == es_code:
        return "ES (España)"
    if geo == eu_code:
        return f"{eu_code} (UE-27)"
    return geo


def _save_plotly_html(fig: go.Figure, out_path: Path) -> None:
    fig.write_html(str(out_path), include_plotlyjs="cdn", full_html=True)
    print(f"HTML guardado en: {out_path.resolve()}")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")
    print(f"Resumen guardado en: {path.resolve()}")


def _safe_float(x: object) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x: object) -> Optional[int]:
    try:
        if pd.isna(x):
            return None
        return int(x)
    except Exception:
        return None


# ----------------------------
# Vista 1: Top 15 (barras)
# ----------------------------
def build_vista1_interactive(top15_df: pd.DataFrame, series_df: pd.DataFrame, rank_df: pd.DataFrame, focus: FocusConfig) -> Tuple[Path, Path, Path]:
    print("Generando Vista 1 interactiva (Top 15, último año)...")

    df = top15_df.copy()
    df["geo"] = df["geo"].astype(str)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    last_year = int(df["year"].max())
    df["geo_label"] = df["geo"].apply(lambda g: _format_geo_label(g, focus.eu_code, focus.es_code))

    # Orden por valor (ascendente para barras horizontales)
    df_val = df.sort_values("value", ascending=True).reset_index(drop=True)
    y_by_value = df_val["geo_label"].tolist()

    # Orden por nombre
    y_by_name = sorted(df["geo_label"].tolist())

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_val["value"],
            y=df_val["geo_label"],
            orientation="h",
            text=[f"{v:.1f}%" for v in df_val["value"]],
            textposition="outside",
            hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"Adopción de IA (empresas que usan IA) — Top 15 países ({last_year})",
        xaxis_title="Porcentaje de empresas (%)",
        yaxis_title="País/área",
        margin=dict(l=40, r=40, t=80, b=40),
        yaxis=dict(categoryorder="array", categoryarray=y_by_value),
    )

    # Controles: ordenar por valor vs por nombre (sin depender del hover)
    fig.update_layout(
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                x=1.02,
                y=1.05,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(
                        label="Ordenar por valor",
                        method="relayout",
                        args=[{"yaxis.categoryorder": "array", "yaxis.categoryarray": y_by_value}],
                    ),
                    dict(
                        label="Ordenar por nombre",
                        method="relayout",
                        args=[{"yaxis.categoryorder": "array", "yaxis.categoryarray": y_by_name}],
                    ),
                ],
            )
        ]
    )

    out_html = CHARTS_DIR / "vista1_top15_last_year_interactive.html"
    _save_plotly_html(fig, out_html)

    # Tabla accesible (CSV)
    out_table = CHARTS_DIR / "vista1_table.csv"
    df_val[["geo", "geo_label", "year", "value"]].to_csv(out_table, index=False, encoding="utf-8")
    print(f"Tabla guardada en: {out_table.resolve()}")

    # Resumen textual (no depende de hover)
    series_last = series_df.copy()
    series_last["geo"] = series_last["geo"].astype(str)
    series_last["year"] = pd.to_numeric(series_last["year"], errors="coerce").astype("Int64")
    series_last["value"] = pd.to_numeric(series_last["value"], errors="coerce")
    series_last = series_last[series_last["year"] == last_year].dropna(subset=["value"])

    top_geo = str(series_last.sort_values("value", ascending=False).iloc[0]["geo"])
    top_val = float(series_last.sort_values("value", ascending=False).iloc[0]["value"])

    es_val = series_last.loc[series_last["geo"] == focus.es_code, "value"]
    eu_val = series_last.loc[series_last["geo"] == focus.eu_code, "value"]
    es_val_f = _safe_float(es_val.iloc[0]) if len(es_val) else None
    eu_val_f = _safe_float(eu_val.iloc[0]) if len(eu_val) else None
    gap = (es_val_f - eu_val_f) if (es_val_f is not None and eu_val_f is not None) else None

    es_rank = rank_df.copy()
    es_rank["geo"] = es_rank["geo"].astype(str)
    es_rank["year"] = pd.to_numeric(es_rank["year"], errors="coerce").astype("Int64")
    es_rank["rank"] = pd.to_numeric(es_rank["rank"], errors="coerce").astype("Int64")
    es_rank_val = es_rank.loc[(es_rank["geo"] == focus.es_code) & (es_rank["year"] == last_year), "rank"]
    es_rank_i = _safe_int(es_rank_val.iloc[0]) if len(es_rank_val) else None

    summary_lines = [
        f"Vista 1 (Top 15, {last_year})",
        f"- Líder (todas las geografías disponibles): {top_geo} con {top_val:.1f}%.",
    ]
    if es_val_f is not None:
        summary_lines.append(f"- España (ES): {es_val_f:.1f}%.")
    if eu_val_f is not None:
        summary_lines.append(f"- UE-27 ({focus.eu_code}): {eu_val_f:.1f}%.")
    if gap is not None:
        summary_lines.append(f"- Brecha ES–UE: {gap:+.1f} puntos porcentuales.")
    if es_rank_i is not None:
        summary_lines.append(f"- Posición de España en el ranking ({last_year}): {es_rank_i}.")

    out_summary = CHARTS_DIR / "vista1_summary.txt"
    _write_text(out_summary, "\n".join(summary_lines))

    return out_html, out_table, out_summary


# ----------------------------
# Vista 2: Tendencia (líneas + dropdown)
# ----------------------------
def build_vista2_interactive(series_df: pd.DataFrame, focus: FocusConfig) -> Tuple[Path, Path, Path]:
    print("Generando Vista 2 interactiva (Tendencia 2021–2025 con dropdown)...")

    df = series_df.copy()
    df["geo"] = df["geo"].astype(str)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[df["geo"].isin(focus.focus_geos)].dropna(subset=["year", "value"]).copy()
    df["geo_label"] = df["geo"].apply(lambda g: _format_geo_label(g, focus.eu_code, focus.es_code))

    year_min = int(df["year"].min())
    year_max = int(df["year"].max())

    # Construir trazas (una por país) y dejar visible todo por defecto
    geo_labels = sorted(df["geo_label"].unique().tolist())
    label_to_geo = { _format_geo_label(g, focus.eu_code, focus.es_code): g for g in focus.focus_geos }

    fig = go.Figure()
    for lab in geo_labels:
        geo_code = label_to_geo.get(lab, None)
        sub = df[df["geo_label"] == lab].sort_values("year")
        fig.add_trace(
            go.Scatter(
                x=sub["year"],
                y=sub["value"],
                mode="lines+markers",
                name=lab,
                hovertemplate=f"{lab} — Año: %{{x}}<br>Valor: %{{y:.2f}}%<extra></extra>",
            )
        )

    # Dropdown: Todos + cada país
    n_traces = len(fig.data)

    def vis_all() -> List[bool]:
        return [True] * n_traces

    def vis_only(label: str) -> List[bool]:
        return [d.name == label for d in fig.data]

    buttons = [
        dict(
            label="Todos",
            method="update",
            args=[{"visible": vis_all()}, {"title": f"Evolución adopción IA ({year_min}–{year_max}) — países foco"}],
        )
    ]
    for lab in geo_labels:
        buttons.append(
            dict(
                label=lab,
                method="update",
                args=[{"visible": vis_only(lab)}, {"title": f"Evolución adopción IA ({year_min}–{year_max}) — {lab}"}],
            )
        )

    fig.update_layout(
        title=f"Evolución adopción IA ({year_min}–{year_max}) — países foco",
        xaxis_title="Año",
        yaxis_title="Porcentaje de empresas (%)",
        xaxis=dict(dtick=1),
        yaxis_tickformat=".0f",
        legend_title_text="País/área (clic para ocultar/mostrar)",
        margin=dict(l=40, r=40, t=80, b=40),
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                x=1.02,
                y=1.05,
                xanchor="left",
                yanchor="top",
                buttons=buttons,
            ),
            dict(
                type="buttons",
                direction="left",
                x=1.02,
                y=0.95,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(
                        label="Reset (mostrar todo)",
                        method="update",
                        args=[{"visible": vis_all()}, {"title": f"Evolución adopción IA ({year_min}–{year_max}) — países foco"}],
                    )
                ],
            ),
        ],
    )

    out_html = CHARTS_DIR / "vista2_trend_focus_interactive.html"
    _save_plotly_html(fig, out_html)

    # Tabla accesible (CSV)
    out_table = CHARTS_DIR / "vista2_table.csv"
    df[["geo", "geo_label", "year", "value"]].to_csv(out_table, index=False, encoding="utf-8")
    print(f"Tabla guardada en: {out_table.resolve()}")

    # Resumen textual (ES vs UE)
    def get_val(geo_code: str, year: int) -> Optional[float]:
        s = df.loc[(df["geo"] == geo_code) & (df["year"] == year), "value"]
        return _safe_float(s.iloc[0]) if len(s) else None

    es_21 = get_val(focus.es_code, year_min)
    es_25 = get_val(focus.es_code, year_max)
    eu_21 = get_val(focus.eu_code, year_min)
    eu_25 = get_val(focus.eu_code, year_max)

    delta_es = (es_25 - es_21) if (es_21 is not None and es_25 is not None) else None
    delta_eu = (eu_25 - eu_21) if (eu_21 is not None and eu_25 is not None) else None
    gap_21 = (es_21 - eu_21) if (es_21 is not None and eu_21 is not None) else None
    gap_25 = (es_25 - eu_25) if (es_25 is not None and eu_25 is not None) else None
    gap_change = (gap_25 - gap_21) if (gap_21 is not None and gap_25 is not None) else None

    summary_lines = [
        f"Vista 2 (Tendencia, {year_min}–{year_max})",
    ]
    if es_21 is not None and es_25 is not None:
        summary_lines.append(f"- España: {es_21:.1f}% → {es_25:.1f}% ({delta_es:+.1f} p.p.).")
    if eu_21 is not None and eu_25 is not None:
        summary_lines.append(f"- UE-27: {eu_21:.1f}% → {eu_25:.1f}% ({delta_eu:+.1f} p.p.).")
    if gap_21 is not None and gap_25 is not None:
        summary_lines.append(f"- Brecha ES–UE: {gap_21:+.1f} p.p. → {gap_25:+.1f} p.p. (cambio: {gap_change:+.1f} p.p.).")
    summary_lines.append("- Interacción: usar el desplegable para aislar un país o la leyenda para ocultar/mostrar series.")

    out_summary = CHARTS_DIR / "vista2_summary.txt"
    _write_text(out_summary, "\n".join(summary_lines))

    return out_html, out_table, out_summary


# ----------------------------
# Vista 3: Ranking (bump + dropdown de conjuntos)
# ----------------------------
def build_vista3_interactive(rank_df: pd.DataFrame, series_df: pd.DataFrame, focus: FocusConfig) -> Tuple[Path, Path, Path]:
    print("Generando Vista 3 interactiva (Ranking / bump con conjuntos)...")

    df = rank_df.copy()
    df["geo"] = df["geo"].astype(str)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["year", "rank", "value"]).copy()

    last_year = int(df["year"].max())

    # Top 15 del último año + foco
    top15_geos = (
        df[df["year"] == last_year]
        .sort_values("rank", ascending=True)
        .head(15)["geo"]
        .astype(str)
        .tolist()
    )
    keep_geos = sorted(set(top15_geos) | set(focus.focus_geos))

    df = df[df["geo"].isin(keep_geos)].copy()
    df["geo_label"] = df["geo"].apply(lambda g: _format_geo_label(g, focus.eu_code, focus.es_code))

    # Top 10 (del último año, dentro de los que ya mantenemos)
    top10_geos = (
        df[df["year"] == last_year]
        .sort_values("rank", ascending=True)
        .head(10)["geo"]
        .astype(str)
        .tolist()
    )
    focus_set = set(focus.focus_geos)
    top10_set = set(top10_geos)
    top15_set = set(keep_geos)

    labels = sorted(df["geo_label"].unique().tolist())
    label_to_geo: Dict[str, str] = {}
    for g in keep_geos:
        label_to_geo[_format_geo_label(g, focus.eu_code, focus.es_code)] = g

    fig = go.Figure()
    for lab in labels:
        geo_code = label_to_geo.get(lab)
        sub = df[df["geo"] == geo_code].sort_values("year")
        fig.add_trace(
            go.Scatter(
                x=sub["year"],
                y=sub["rank"],
                mode="lines+markers",
                name=lab,
                hovertemplate=f"{lab} — Año: %{{x}}<br>Rank: %{{y}}<extra></extra>",
            )
        )

    n_traces = len(fig.data)

    def vis_for_set(geo_set: set[str]) -> List[bool]:
        vis: List[bool] = []
        for tr in fig.data:
            geo_code = label_to_geo.get(tr.name, "")
            vis.append(geo_code in geo_set)
        return vis

    buttons = [
        dict(
            label="Top 10 (último año)",
            method="update",
            args=[{"visible": vis_for_set(top10_set)}, {"title": f"Ranking adopción IA — Top 10 ({last_year})"}],
        ),
        dict(
            label="Top 15 (último año)",
            method="update",
            args=[{"visible": vis_for_set(top15_set)}, {"title": f"Ranking adopción IA — Top 15 ({last_year})"}],
        ),
        dict(
            label="Foco (UE/ES + comparadores)",
            method="update",
            args=[{"visible": vis_for_set(focus_set)}, {"title": "Ranking adopción IA — países foco"}],
        ),
    ]

    fig.update_layout(
        title=f"Ranking adopción IA — Top 15 ({last_year})",
        xaxis_title="Año",
        yaxis_title="Posición en el ranking (1 = mejor)",
        xaxis=dict(dtick=1),
        yaxis=dict(autorange="reversed", dtick=1),
        legend_title_text="País/área (clic para ocultar/mostrar)",
        margin=dict(l=40, r=40, t=80, b=40),
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                x=1.02,
                y=1.05,
                xanchor="left",
                yanchor="top",
                buttons=buttons,
            ),
            dict(
                type="buttons",
                direction="left",
                x=1.02,
                y=0.95,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(
                        label="Reset (Top 15)",
                        method="update",
                        args=[{"visible": vis_for_set(top15_set)}, {"title": f"Ranking adopción IA — Top 15 ({last_year})"}],
                    )
                ],
            ),
        ],
    )

    out_html = CHARTS_DIR / "vista3_bump_ranking_interactive.html"
    _save_plotly_html(fig, out_html)

    # Tabla accesible (CSV)
    out_table = CHARTS_DIR / "vista3_table.csv"
    df[["geo", "geo_label", "year", "value", "rank"]].to_csv(out_table, index=False, encoding="utf-8")
    print(f"Tabla guardada en: {out_table.resolve()}")

    # Resumen textual (ES y UE)
    def get_rank(geo_code: str, year: int) -> Optional[int]:
        s = df.loc[(df["geo"] == geo_code) & (df["year"] == year), "rank"]
        return _safe_int(s.iloc[0]) if len(s) else None

    years = sorted(df["year"].unique().tolist())
    year_min = int(min(years))
    year_max = int(max(years))

    es_r_min = get_rank(focus.es_code, year_min)
    es_r_max = get_rank(focus.es_code, year_max)
    eu_r_min = get_rank(focus.eu_code, year_min)
    eu_r_max = get_rank(focus.eu_code, year_max)

    summary_lines = [
        f"Vista 3 (Ranking / bump, {year_min}–{year_max})",
    ]
    if es_r_min is not None and es_r_max is not None:
        summary_lines.append(f"- España: rank {es_r_min} → {es_r_max} (mejora si baja el número).")
    if eu_r_min is not None and eu_r_max is not None:
        summary_lines.append(f"- UE-27: rank {eu_r_min} → {eu_r_max}.")
    summary_lines.append("- Interacción: usar el desplegable para cambiar el conjunto de países (Top 10, Top 15 o foco) y la leyenda para filtrar manualmente.")

    out_summary = CHARTS_DIR / "vista3_summary.txt"
    _write_text(out_summary, "\n".join(summary_lines))

    return out_html, out_table, out_summary


def main() -> int:
    print("Iniciando generación de interactividad (Plotly + tablas + resúmenes)...")
    _ensure_dirs()

    top15 = _load_csv(TOP15_PATH, "adoption_top15_last_year.csv")
    series = _load_csv(SERIES_PATH, "adoption_country_year.csv")
    rank = _load_csv(RANK_PATH, "adoption_country_year_rank.csv")

    focus = _detect_focus(series)
    print(f"Foco detectado: UE={focus.eu_code}, ES={focus.es_code}, países foco={focus.focus_geos}")

    # Vista 1
    build_vista1_interactive(top15, series, rank, focus)

    # Vista 2
    build_vista2_interactive(series, focus)

    # Vista 3
    build_vista3_interactive(rank, series, focus)

    print("Interactividad generada correctamente.")
    print("Salidas en outputs/charts/:")
    print("- HTML: vista1_*_interactive.html, vista2_*_interactive.html, vista3_*_interactive.html")
    print("- Tablas: vista1_table.csv, vista2_table.csv, vista3_table.csv")
    print("- Resúmenes: vista1_summary.txt, vista2_summary.txt, vista3_summary.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
