import { getCallers, getGraph, queryCodebase } from "./api-client.js";
import { initCharts, updateCharts } from "./charts.js";
import { renderGraph } from "./graph.js";
import {
  clearQueryLoading,
  renderAnswer,
  renderCallers,
  renderDiagnostics,
  renderQueryError,
  renderSources,
  setGraphEmpty,
  setQueryLoading,
  setStatus,
  streamAnswer,
} from "./ui.js";

const queryForm = document.getElementById("query-form");
const queryInput = document.getElementById("query-input");
const graphForm = document.getElementById("graph-form");
const symbolInput = document.getElementById("symbol-input");
const chips = document.querySelectorAll(".chip");
let chartLibReady = false;
let graphLibReady = false;
let activeQueryRun = 0;

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
  const runId = activeQueryRun + 1;
  activeQueryRun = runId;
  setQueryLoading();
  try {
    const payload = await queryCodebase(query);
    await ensureChartLib();
    if (runId !== activeQueryRun) {
      return;
    }
    clearQueryLoading();
    renderSources(payload.sources || []);
    renderDiagnostics(payload.diagnostics || {});
    updateCharts(payload.diagnostics || {});
    setStatus("Responding");
    await streamAnswer(payload.answer);
    if (runId !== activeQueryRun) {
      return;
    }
    setStatus("Ready");
  } catch (error) {
    if (runId !== activeQueryRun) {
      return;
    }
    renderAnswer("Query failed.");
    renderSources([]);
    renderDiagnostics({});
    updateCharts({});
    renderQueryError(error);
    setStatus("Error");
  } finally {
    if (runId === activeQueryRun) {
      clearQueryLoading();
    }
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
