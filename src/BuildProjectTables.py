from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


IN_PATH = Path("data/processed/ai_clean.csv")
OUT_DIR = Path("outputs")
REPORT_PATH = OUT_DIR / "build_tables_report.txt"

# Elegir códigos principales del proyecto
NACE_TOTAL = "C10-S951_X_K"  # Total de actividades cubiertas (sin sector financiero)
INDIC_ADOPTION = "E_AI_TANY"  # Empresas que usan al menos una tecnología de IA

# Elegir tecnologías (subconjunto manejable para un gráfico comparativo)
AI_TECH_INDIC: Dict[str, str] = {
    "E_AI_TTM": "Text mining (análisis de texto)",
    "E_AI_TSR": "Reconocimiento de voz",
    "E_AI_TNLG": "Generación de lenguaje (texto/voz/código)",
    "E_AI_TIR": "Reconocimiento de imágenes",
    "E_AI_TML": "Machine learning (entrenamiento de modelos)",
    "E_AI_TPA": "Robots/autonomía (automatización física)",
    "E_AI_TAR": "Automatización de procesos con IA",
    "E_AI_TPVSG": "Generación de imagen/vídeo/audio",
}

# Comparadores para foco narrativo (se selecciona el primero que exista)
EU_CANDIDATES = ["EU27_2020", "EU27", "EU"]


@dataclass(frozen=True)
class GeoFocus:
    eu_code: Optional[str]
    es_code: Optional[str]
    focus_list: List[str]


def _ensure_out_dir() -> None:
    # Crear carpeta outputs si no existe
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_data(path: Path) -> pd.DataFrame:
    # Cargar dataset limpio y validar columnas
    print("Cargando dataset limpio...")
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra: {path} (ejecutar antes CleanData.py)")

    df = pd.read_csv(path, low_memory=False)

    required = {"geo", "year", "value", "indic_is", "nace_r2", "size_emp"}
    missing = sorted(list(required - set(df.columns)))
    if missing:
        raise RuntimeError(f"Faltan columnas requeridas: {missing}")

    print(f"Dataset cargado correctamente. Filas: {len(df)}, Columnas: {df.shape[1]}")
    return df


def _pick_first_existing(values: List[str], available: List[str]) -> Optional[str]:
    # Elegir el primer código disponible de una lista de candidatos
    avail_set = set(available)
    for v in values:
        if v in avail_set:
            return v
    return None


def _detect_geo_focus(df: pd.DataFrame) -> GeoFocus:
    # Detectar códigos de UE y España si existen en el dataset
    geos = sorted(df["geo"].dropna().astype(str).unique().tolist())
    eu = _pick_first_existing(EU_CANDIDATES, geos)
    es = "ES" if "ES" in set(geos) else None

    focus: List[str] = []
    if eu:
        focus.append(eu)
    if es:
        focus.append(es)
    # Añadir comparadores típicos si existen
    for cand in ["DE", "FR", "IT", "PT", "NL"]:
        if cand in set(geos) and cand not in focus:
            focus.append(cand)

    return GeoFocus(eu_code=eu, es_code=es, focus_list=focus)


def _write_report(lines: List[str]) -> None:
    # Escribir informe de tablas generadas
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print("Iniciando construcción de tablas del proyecto...")
    _ensure_out_dir()

    df = _load_data(IN_PATH)

    report: List[str] = []
    report.append("INFORME DE TABLAS (BuildProjectTables.py)")
    report.append(f"Entrada: {IN_PATH.as_posix()}")
    report.append(f"Filas totales: {len(df)}")
    report.append("")

    # Detectar año final disponible
    years = sorted(df["year"].dropna().unique().tolist())
    if not years:
        raise RuntimeError("No se han detectado años en el dataset.")
    year_min, year_max = int(years[0]), int(years[-1])

    print(f"Años disponibles: {year_min} → {year_max}")
    report.append(f"Años disponibles: {year_min} → {year_max}")

    # Detectar foco geo
    geo_focus = _detect_geo_focus(df)
    print(f"Geo UE detectado: {geo_focus.eu_code}")
    print(f"Geo España detectado: {geo_focus.es_code}")
    print(f"Geo foco: {geo_focus.focus_list}")

    report.append(f"Geo UE detectado: {geo_focus.eu_code}")
    report.append(f"Geo España detectado: {geo_focus.es_code}")
    report.append(f"Geo foco: {geo_focus.focus_list}")
    report.append("")

    # 1) Adopción por país-año (total actividades, indicador principal)
    print("Generando tabla 1: adopción por país y año (E_AI_TANY, total NACE)...")
    adoption = df[
        (df["indic_is"] == INDIC_ADOPTION) &
        (df["nace_r2"] == NACE_TOTAL)
    ][["geo", "year", "value"]].copy()

    if adoption.empty:
        raise RuntimeError("Tabla de adopción vacía: revisar códigos INDIC_ADOPTION y NACE_TOTAL.")

    out_adoption = OUT_DIR / "adoption_country_year.csv"
    adoption.to_csv(out_adoption, index=False, encoding="utf-8")
    report.append(f"Tabla 1 creada: {out_adoption.as_posix()} (filas={len(adoption)})")

    # 2) Top países último año
    print("Generando tabla 2: top países último año...")
    top_last = (
        adoption[adoption["year"] == year_max]
        .sort_values("value", ascending=False)
        .head(15)
        .reset_index(drop=True)
    )
    out_top = OUT_DIR / "adoption_top15_last_year.csv"
    top_last.to_csv(out_top, index=False, encoding="utf-8")
    report.append(f"Tabla 2 creada: {out_top.as_posix()} (año={year_max})")

    # 3) Ranking por año (para bump chart)
    print("Generando tabla 3: ranking por año...")
    adoption_rank = adoption.copy()
    adoption_rank["rank"] = (
        adoption_rank.groupby("year")["value"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )
    out_rank = OUT_DIR / "adoption_country_year_rank.csv"
    adoption_rank.to_csv(out_rank, index=False, encoding="utf-8")
    report.append(f"Tabla 3 creada: {out_rank.as_posix()}")

    # 4) Sectores (España) último año (excluyendo total)
    print("Generando tabla 4: sectores España último año (E_AI_TANY)...")
    if geo_focus.es_code:
        sectors_es = df[
            (df["geo"] == geo_focus.es_code) &
            (df["year"] == year_max) &
            (df["indic_is"] == INDIC_ADOPTION) &
            (df["nace_r2"] != NACE_TOTAL)
        ][["nace_r2", "value"]].copy()

        # Quedarse con top sectores por valor para mantener manejable
        sectors_es = sectors_es.sort_values("value", ascending=False).head(15).reset_index(drop=True)

        out_sectors_es = OUT_DIR / "sectors_es_top15_last_year.csv"
        sectors_es.to_csv(out_sectors_es, index=False, encoding="utf-8")
        report.append(f"Tabla 4 creada: {out_sectors_es.as_posix()} (año={year_max})")
    else:
        report.append("Tabla 4 no creada: no se ha detectado 'ES' en geo.")

    # 5) Tecnologías (UE y España) último año, total NACE
    print("Generando tabla 5: tecnologías (UE y España) último año (total NACE)...")
    tech_codes = list(AI_TECH_INDIC.keys())

    tech = df[
        (df["year"] == year_max) &
        (df["nace_r2"] == NACE_TOTAL) &
        (df["indic_is"].isin(tech_codes))
    ][["geo", "indic_is", "value"]].copy()

    # Filtrar a UE/ES si están disponibles; si no, dejar sin filtrar
    if geo_focus.focus_list:
        tech = tech[tech["geo"].isin(geo_focus.focus_list)].copy()

    # Añadir etiquetas legibles
    tech["indic_label"] = tech["indic_is"].map(AI_TECH_INDIC).fillna(tech["indic_is"])

    out_tech = OUT_DIR / "ai_tech_focus_last_year.csv"
    tech.to_csv(out_tech, index=False, encoding="utf-8")
    report.append(f"Tabla 5 creada: {out_tech.as_posix()} (año={year_max})")

    # Guardar informe
    _write_report(report)

    print(f"Tablas generadas correctamente en: {OUT_DIR.resolve()}")
    print(f"Informe guardado en: {REPORT_PATH.resolve()}")
    print("Construcción de tablas completada correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
