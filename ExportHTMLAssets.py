# ExportHtmlAssets.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import html

import pandas as pd


@dataclass(frozen=True)
class ViewMeta:
    key: str
    caption: str


VIEWS: dict[str, ViewMeta] = {
    "vista1": ViewMeta(key="vista1", caption="Vista 1 — Top 15 países (último año)"),
    "vista2": ViewMeta(key="vista2", caption="Vista 2 — Evolución temporal (2021–2025)"),
    "vista3": ViewMeta(key="vista3", caption="Vista 3 — Ranking anual (bump chart)"),
}


def _infer_view_key(filename: str) -> Optional[str]:
    # Ejemplos esperados: vista1_table.csv, vista2_summary.txt, etc.
    lower = filename.lower()
    for k in VIEWS.keys():
        if lower.startswith(k):
            return k
    return None


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def csv_to_table_fragment(csv_path: Path, caption: str) -> str:
    df = pd.read_csv(csv_path)

    # Construir tabla HTML accesible (fragmento, sin <html> completo)
    parts: list[str] = []
    parts.append('<table class="data-table">')
    parts.append(f"<caption>{html.escape(caption)}</caption>")
    parts.append("<thead><tr>")
    for col in df.columns:
        parts.append(f'<th scope="col">{html.escape(str(col))}</th>')
    parts.append("</tr></thead>")
    parts.append("<tbody>")

    for _, row in df.iterrows():
        parts.append("<tr>")
        for col in df.columns:
            val = row[col]
            cell = "" if pd.isna(val) else str(val)
            parts.append(f"<td>{html.escape(cell)}</td>")
        parts.append("</tr>")

    parts.append("</tbody></table>")
    return "\n".join(parts)


def txt_to_summary_fragment(txt_path: Path, title: str) -> str:
    txt = txt_path.read_text(encoding="utf-8").strip()
    if not txt:
        return "<p>No hay resumen disponible.</p>"

    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    paragraphs: list[str] = []
    bullets: list[str] = []

    for ln in lines:
        if ln.startswith("-"):
            bullets.append(ln.lstrip("-").strip())
        else:
            paragraphs.append(ln)

    out: list[str] = []
    # Título visible dentro del bloque (texto normal, no <pre>)
    out.append(f"<p><strong>{html.escape(title)}</strong></p>")

    for p in paragraphs:
        out.append(f"<p>{html.escape(p)}</p>")

    if bullets:
        out.append("<ul>")
        for b in bullets:
            out.append(f"<li>{html.escape(b)}</li>")
        out.append("</ul>")

    return "\n".join(out)


def main() -> None:
    docs_dir = Path("docs")
    tables_dir = docs_dir / "tables"
    text_dir = docs_dir / "text"

    if not docs_dir.exists():
        raise SystemExit("No se encuentra la carpeta 'docs/'. Ejecutar este script desde la raíz del proyecto donde exista 'docs/'.")

    # Convertir CSV -> HTML (tabla)
    csv_files = sorted(tables_dir.glob("*.csv"))
    if not csv_files:
        print("No se han encontrado CSV en docs/tables/. Nada que convertir.")
    else:
        print(f"Convirtiendo {len(csv_files)} CSV a tablas HTML...")
        for csv_path in csv_files:
            view_key = _infer_view_key(csv_path.name) or "vista"
            meta = VIEWS.get(view_key)
            caption = meta.caption if meta else f"Tabla — {csv_path.stem}"
            fragment = csv_to_table_fragment(csv_path, caption=caption)
            out_path = csv_path.with_suffix(".html")
            _write_text(out_path, fragment)
            print(f"- OK: {csv_path.name} -> {out_path.name}")

    # Convertir TXT -> HTML (resumen)
    txt_files = sorted(text_dir.glob("*.txt"))
    if not txt_files:
        print("No se han encontrado TXT en docs/text/. Nada que convertir.")
    else:
        print(f"Convirtiendo {len(txt_files)} TXT a resúmenes HTML...")
        for txt_path in txt_files:
            view_key = _infer_view_key(txt_path.name) or "vista"
            meta = VIEWS.get(view_key)
            title = meta.caption if meta else f"Resumen — {txt_path.stem}"
            fragment = txt_to_summary_fragment(txt_path, title=title)
            out_path = txt_path.with_suffix(".html")
            _write_text(out_path, fragment)
            print(f"- OK: {txt_path.name} -> {out_path.name}")

    print("Conversión completada. Se han generado docs/tables/*.html y docs/text/*.html.")


if __name__ == "__main__":
    main()
