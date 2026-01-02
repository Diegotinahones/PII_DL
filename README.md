# Práctica Parte II — Visualización de datos (M2.859)

## Visualización publicada (GitHub Pages)
https://diegotinahones.github.io/PII_DL/

## Repositorio
https://github.com/Diegotinahones/PII_DL

## Estructura del proyecto
- `docs/`: sitio público (HTML/CSS/JS) y recursos embebidos.
  - `index.html`: página principal.
  - `app.js`: lógica de selección de vista y modo (gráfico/tabla/resumen).
  - `styles.css`: estilos.
  - `views/`: HTML de las vistas generadas con Plotly.
  - `tables/`: CSV y tablas HTML generadas a partir de CSV.
  - `text/`: resúmenes HTML generados a partir de TXT.
- `src/`: scripts Python (descarga, limpieza, perfilado, construcción de tablas, generación de vistas y exportación de assets HTML).
- `data/`: datos brutos (`raw/`) y procesados (`processed/`).
- `outputs/`: informes y tablas intermedias de soporte.

## Requisitos
- Python 3
- Dependencias: `pandas`, `plotly`

## Ejecución en local (sitio web)
1. Situarse en la raíz del repositorio (donde existe la carpeta `docs/`).
2. Servir el proyecto por HTTP:
   ```bash
   python3 -m http.server 8000
   ```
3. Abrir en el navegador:
   - `http://localhost:8000/docs/`

## Regeneración de tablas/resúmenes HTML (desde CSV/TXT)
Tras generar/actualizar los CSV y TXT en `docs/tables/` y `docs/text/`, ejecutar:
```bash
python3 src/ExportHTMLAssets.py
```

Esto crea/actualiza:
- `docs/tables/*.html`
- `docs/text/*.html`
