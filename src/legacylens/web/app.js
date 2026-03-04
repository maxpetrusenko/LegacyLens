import { getCallers, getGraph, queryCodebase } from "./api-client.js";
import { initCharts, updateCharts } from "./charts.js";
import { renderGraph } from "./graph.js";
import {
  addToQueryLog,
  clearQueryLoading,
  renderAnswer,
  renderCallers,
  renderDiagnostics,
  renderKpiChips,
  renderQueryLog,
  renderQueryError,
  renderSources,
  setGraphEmpty,
  setQueryLoading,
  setStatus,
  updateSessionStats,
} from "./ui.js";

const queryForm = document.getElementById("query-form");
const queryInput = document.getElementById("query-input");
const graphForm = document.getElementById("graph-form");
const symbolInput = document.getElementById("symbol-input");
const chips = document.querySelectorAll(".chip");

let chartLibReady = false;
let graphLibReady = false;

const session = {
  queryCount: 0,
  similaritySum: 0,
  filesSeen: new Set(),
};

function _updateSessionStats() {
  const avgSimilarity = session.queryCount
    ? session.similaritySum / session.queryCount
    : 0;
  updateSessionStats({
    queryCount: session.queryCount,
    avgSimilarity,
    filesSeen: session.filesSeen.size,
  });
}

function _recordQuery(diagnostics, sources) {
  session.queryCount += 1;
  session.similaritySum += Number(diagnostics.top1_score || 0);
  for (const s of sources || []) {
    session.filesSeen.add(s.file_path);
  }
  _updateSessionStats();
  addToQueryLog({ query: queryInput.value, ts: Date.now() });
  renderKpiChips(diagnostics, sources);
  renderQueryLog();
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.defer = true;
    script.dataset.src = src;
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    });
    script.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)));
    document.head.appendChild(script);
  });
}

async function ensureChartLib() {
  if (chartLibReady) {
    return;
  }
  await loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js");
  initCharts();
  chartLibReady = true;
}

async function ensureGraphLib() {
  if (graphLibReady) {
    return;
  }
  await loadScript("https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js");
  graphLibReady = true;
}

async function runQuery(query) {
  if (!query) {
    return;
  }
  setQueryLoading();
  try {
    const payload = await queryCodebase(query);
    await ensureChartLib();
    renderAnswer(payload.answer);
    renderSources(payload.sources || []);
    renderDiagnostics(payload.diagnostics || {});
    updateCharts(payload.diagnostics || {});
    _recordQuery(payload.diagnostics || {}, payload.sources || []);
    setStatus("Ready");
  } catch (error) {
    renderAnswer("Query failed.");
    renderSources([]);
    renderDiagnostics({});
    updateCharts({});
    renderQueryError(error);
    setStatus("Error");
  } finally {
    clearQueryLoading();
  }
}

async function runGraphLookup(symbol) {
  if (!symbol) {
    return;
  }
  setStatus("Mapping");
  try {
    await ensureGraphLib();
    const [callersData, graphData] = await Promise.all([getCallers(symbol), getGraph(symbol)]);
    renderCallers(callersData.callers || []);
    renderGraph(graphData);
    setGraphEmpty(!(graphData.edges || []).length);
    setStatus("Ready");
  } catch (error) {
    renderCallers([`Lookup failed: ${String(error)}`]);
    setGraphEmpty(true);
    setStatus("Error");
  }
}

queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runQuery(queryInput.value.trim());
});

graphForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runGraphLookup(symbolInput.value.trim());
});

for (const chip of chips) {
  chip.addEventListener("click", async () => {
    const q = chip.dataset.q || "";
    queryInput.value = q;
    await runQuery(q);
  });
}

document.addEventListener("keydown", async (event) => {
  const activeTag = document.activeElement?.tagName || "";
  const inInput = activeTag === "INPUT" || activeTag === "TEXTAREA";
  if (event.key === "/" && !inInput) {
    event.preventDefault();
    queryInput.focus();
  }
  if (event.key === "Enter" && document.activeElement === queryInput && !event.shiftKey) {
    event.preventDefault();
    await runQuery(queryInput.value.trim());
  }
});

setStatus("Ready");
setGraphEmpty(true);
renderQueryLog();
