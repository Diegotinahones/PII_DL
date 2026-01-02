#!/usr/bin/env python3
"""
Descargar dataset de Eurostat vía SDMX 3.0 (SDMX-CSV 2.0) con fallback de dataflow y soporte asíncrono.

Ejecución:
  python3 DownloadData.py

Salida:
  data/raw/eurostat_ai.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import time
import xml.etree.ElementTree as ET


# Aceptación oficial para SDMX-CSV 2.0.0 (labels=id para estabilidad)
ACCEPT_SDMXCSV_2 = "application/vnd.sdmx.data+csv;version=2.0.0;labels=id"

# Base SDMX 3.0 (data query)
EUROSTAT_SDMX3_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT"

# Base Async (Eurostat)
EUROSTAT_ASYNC_BASE = "https://ec.europa.eu/eurostat/api/dissemination/1.0/async"

# Candidatos (primero el actual, luego el antiguo por compatibilidad)
DATAFLOW_CANDIDATES = ("ISOC_EB_AIN2", "ISOC_E_AIN2")

# Parámetros de consulta para aligerar (mantener datos, sin atributos)
QUERY_PARAMS = {
    "attributes": "none",
    "measures": "all",
}

# Control de polling asíncrono
ASYNC_POLL_SECONDS = 5
ASYNC_MAX_POLLS = 120  # 10 minutos aprox. (120 * 5s)


@dataclass(frozen=True)
class HttpResult:
    content: bytes
    content_type: str


def _http_get(url: str, accept: str) -> HttpResult:
    """Hacer GET y devolver contenido + content-type."""
    req = Request(url, headers={"Accept": accept, "User-Agent": "uoc-viz-accessibility-script/1.0"})
    with urlopen(req, timeout=60) as resp:
        content_type = resp.headers.get("Content-Type", "")
        data = resp.read()
        return HttpResult(content=data, content_type=content_type)


def _looks_like_async_envelope(xml_bytes: bytes) -> bool:
    """Detectar si la respuesta parece un sobre SOAP de extracción asíncrona."""
    head = xml_bytes.lstrip()[:200].lower()
    return (b"<env:envelope" in head) or (b"<soap" in head) or (b"<s:envelope" in head)


def _extract_async_id(xml_bytes: bytes) -> Optional[str]:
    """Extraer el <id> de la respuesta SOAP (Step 1)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    # Buscar cualquier elemento cuyo tag termine en 'id'
    for el in root.iter():
        if el.tag.lower().endswith("id") and el.text:
            candidate = el.text.strip()
            # Heurística simple: los ids suelen ser UUID con guiones
            if len(candidate) >= 30 and "-" in candidate:
                return candidate
    return None


def _extract_async_status(xml_bytes: bytes) -> Optional[str]:
    """Extraer el <status> de la respuesta SOAP (Step 2)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    # Hay varios <status>; quedarse con el que parezca estado operativo (SUBMITTED/PROCESSING/AVAILABLE/...)
    statuses = []
    for el in root.iter():
        if el.tag.lower().endswith("status") and el.text:
            statuses.append(el.text.strip().upper())

    # Devolver el último conocido que encaje
    for st in reversed(statuses):
        if st in {"SUBMITTED", "PROCESSING", "AVAILABLE", "EXPIRED", "UNKNOWN_REQUEST", "ERROR"}:
            return st
    return statuses[-1] if statuses else None


def _async_status_url(req_id: str) -> str:
    return f"{EUROSTAT_ASYNC_BASE}/status/{req_id}"


def _async_data_url(req_id: str) -> str:
    return f"{EUROSTAT_ASYNC_BASE}/data/{req_id}"


def _run_async_flow(initial_xml: bytes) -> bytes:
    """Gestionar Step 1->2->3 y devolver el CSV final."""
    req_id = _extract_async_id(initial_xml)
    if not req_id:
        raise RuntimeError("Respuesta asíncrona detectada, pero no se ha podido extraer el id de solicitud.")

    print(f"Respuesta asíncrona detectada. ID de extracción: {req_id}")
    print("Consultando estado de la extracción...")

    for i in range(1, ASYNC_MAX_POLLS + 1):
        status_res = _http_get(_async_status_url(req_id), accept="application/xml")
        status = _extract_async_status(status_res.content) or "DESCONOCIDO"
        print(f"Estado ({i}/{ASYNC_MAX_POLLS}): {status}")

        if status == "AVAILABLE":
            print("Datos disponibles. Descargando resultado...")
            data_res = _http_get(_async_data_url(req_id), accept=ACCEPT_SDMXCSV_2)
            return data_res.content

        if status in {"EXPIRED", "UNKNOWN_REQUEST", "ERROR"}:
            raise RuntimeError(f"Extracción asíncrona fallida o expirada. Estado: {status}")

        time.sleep(ASYNC_POLL_SECONDS)

    raise RuntimeError("Tiempo máximo de espera alcanzado en extracción asíncrona (no llegó a AVAILABLE).")


def _build_sdmx3_url(dataflow_id: str) -> str:
    """Construir URL SDMX3 para descargar dataset completo (con parámetros)."""
    base = f"{EUROSTAT_SDMX3_BASE}/{dataflow_id}/1.0"
    return f"{base}?{urlencode(QUERY_PARAMS)}"


def main() -> None:
    out_path = Path("data/raw/eurostat_ai.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Iniciando descarga de datos (Eurostat SDMX 3.0 / SDMX-CSV 2.0)...")

    last_error: Optional[str] = None

    for idx, dataflow_id in enumerate(DATAFLOW_CANDIDATES, start=1):
        url = _build_sdmx3_url(dataflow_id)
        print(f"Intentando descarga ({idx}/{len(DATAFLOW_CANDIDATES)}): {dataflow_id}")
        print(f"URL: {url}")

        try:
            res = _http_get(url, accept=ACCEPT_SDMXCSV_2)
            content = res.content

            # Detectar respuesta asíncrona (SOAP) y resolverla si aparece
            if _looks_like_async_envelope(content):
                content = _run_async_flow(content)

            # Validar que parece CSV (mínimo)
            if b"," not in content[:2000] and b"STRUCTURE" not in content[:2000].upper():
                raise RuntimeError("La respuesta no parece SDMX-CSV (posible error o formato inesperado).")

            out_path.write_bytes(content)
            print(f"Dataset guardado correctamente en: {out_path.resolve()}")
            print("Descarga completada correctamente.")
            return

        except HTTPError as e:
            last_error = f"HTTP {e.code} - {getattr(e, 'reason', 'Error')}"
            print(f"Error en descarga: {last_error}")
        except URLError as e:
            last_error = f"URLError - {e.reason}"
            print(f"Error en descarga: {last_error}")
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"Error en descarga: {last_error}")

    print("No se ha podido descargar el dataset con ningún dataflow candidato.")
    print(f"Último error: {last_error}")
    print("Acción recomendada: revisar el dataset en el Data Browser y ajustar DATAFLOW_CANDIDATES si fuese necesario.")


if __name__ == "__main__":
    main()
