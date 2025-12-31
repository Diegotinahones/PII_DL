// docs/app.js
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const viewSelect = $("#viewSelect");
  const displaySelect = $("#displaySelect");

  const chartBlock = $("#chartBlock");
  const tableBlock = $("#tableBlock");
  const summaryBlock = $("#summaryBlock");

  const chartFrame = $("#chartFrame");

  const csvLink = $("#csvLink");
  const tableHtmlLink = $("#tableHtmlLink");
  const summaryHtmlLink = $("#summaryHtmlLink");

  const tableContainer = $("#tableContainer");
  const summaryBox = $("#summaryBox");

  const CONFIG = {
    vista1: {
      label: "Vista 1 — Top 15 países (último año)",
      iframeSrc: "./views/vista1_top15_last_year_interactive.html",
      csvSrc: "./tables/vista1_table.csv",
      tableHtmlSrc: "./tables/vista1_table.html",
      summaryHtmlSrc: "./text/vista1_summary.html",
    },
    vista2: {
      label: "Vista 2 — Evolución temporal (2021–2025)",
      iframeSrc: "./views/vista2_trend_focus_interactive.html",
      csvSrc: "./tables/vista2_table.csv",
      tableHtmlSrc: "./tables/vista2_table.html",
      summaryHtmlSrc: "./text/vista2_summary.html",
    },
    vista3: {
      label: "Vista 3 — Ranking anual (bump chart)",
      iframeSrc: "./views/vista3_bump_ranking_interactive.html",
      csvSrc: "./tables/vista3_table.csv",
      tableHtmlSrc: "./tables/vista3_table.html",
      summaryHtmlSrc: "./text/vista3_summary.html",
    },
  };

  let state = { view: "vista1", display: "table" };

  function setVisibility(displayMode) {
    chartBlock.hidden = displayMode !== "chart";
    tableBlock.hidden = displayMode !== "table";
    summaryBlock.hidden = displayMode !== "summary";
  }

  async function fetchHtmlFragment(path) {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`No se ha podido cargar: ${path} (HTTP ${res.status})`);
    return await res.text();
  }

  async function loadTable(viewKey) {
    const view = CONFIG[viewKey];
    tableContainer.innerHTML = `<p class="hint">Cargando tabla…</p>`;
    try {
      const fragment = await fetchHtmlFragment(view.tableHtmlSrc);
      tableContainer.innerHTML = fragment;
    } catch (e) {
      tableContainer.innerHTML =
        `<p class="hint">No se ha podido cargar la tabla ahora mismo (revisar que la web se está sirviendo por HTTP).</p>`;
      console.error(e);
    }
  }

  async function loadSummary(viewKey) {
    const view = CONFIG[viewKey];
    summaryBox.innerHTML = `<p class="hint">Cargando resumen…</p>`;
    try {
      const fragment = await fetchHtmlFragment(view.summaryHtmlSrc);
      summaryBox.innerHTML = fragment;
    } catch (e) {
      summaryBox.innerHTML =
        `<p class="hint">No se ha podido cargar el resumen ahora mismo (revisar que la web se está sirviendo por HTTP).</p>`;
      console.error(e);
    }
  }

  async function applyView(viewKey) {
    const view = CONFIG[viewKey];
    state.view = viewKey;

    chartFrame.src = view.iframeSrc;
    chartFrame.title = view.label;

    csvLink.href = view.csvSrc;
    tableHtmlLink.href = view.tableHtmlSrc;
    summaryHtmlLink.href = view.summaryHtmlSrc;

    if (state.display === "table") await loadTable(viewKey);
    if (state.display === "summary") await loadSummary(viewKey);
  }

  async function applyDisplay(displayMode) {
    state.display = displayMode;
    setVisibility(displayMode);

    if (displayMode === "table") await loadTable(state.view);
    if (displayMode === "summary") await loadSummary(state.view);
  }

  function init() {
    viewSelect.value = state.view;
    displaySelect.value = state.display;

    setVisibility(state.display);
    applyView(state.view);

    viewSelect.addEventListener("change", () => applyView(viewSelect.value));
    displaySelect.addEventListener("change", () => applyDisplay(displaySelect.value));
  }

  document.addEventListener("DOMContentLoaded", init);
})();
