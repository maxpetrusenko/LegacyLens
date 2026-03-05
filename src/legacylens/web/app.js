import { getCallers, getGraph, getMeta, queryCodebase } from "./api-client.js";
import { initCharts, updateCharts } from "./charts.js";
import { renderGraph, getGraphStats } from "./graph.js";
import {
  addToQueryLog,
  clearQueryLog,
  clearQueryLoading,
  renderAnswer,
  renderCallers,
  renderDiagnostics,
  renderGraphLegend,
  renderGraphStats,
  renderKpiChips,
  renderMetaStrip,
  renderQueryLog,
  renderQueryError,
  renderSources,
  setFusionEnabled,
  setGraphEmpty,
  setStatus,
  setQueryLoading,
  toggleMetaDetails,
  updateSessionStats,
} from "./ui.js";

const queryForm = document.getElementById("query-form");
const queryInput = document.getElementById("query-input");
const graphForm = document.getElementById("graph-form");
const symbolInput = document.getElementById("symbol-input");
const chips = document.querySelectorAll(".chip");
const clearLogBtn = document.getElementById("clear-log-btn");
const fusionToggle = document.getElementById("fusion-toggle");
const metaToggle = document.getElementById("meta-toggle");
const themeToggle = document.getElementById("theme-toggle");

let chartLibReady = false;
let graphLibReady = false;
let fusionEnabled = false;
let theme = "light";
let lastSources = [];

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
  addToQueryLog({ query: queryInput.value, ts: Date.now(), topScore: Number(diagnostics.top1_score || 0) });
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
    const sources = payload.sources || [];
    lastSources = sources;
    renderSources(sources);
    renderDiagnostics(payload.diagnostics || {});
    renderMetaStrip({}, payload.query_meta || {});
    updateCharts(payload.diagnostics || {}, sources);
    _recordQuery(payload.diagnostics || {}, sources);
    const inferredSymbol = inferGraphSymbol(query, sources);
    if (inferredSymbol) {
      symbolInput.value = inferredSymbol;
      await runGraphLookup(inferredSymbol, { allowFallback: true, silentStatus: true });
    }
    setStatus("Ready");
  } catch (error) {
    renderAnswer("Query failed.");
    renderSources([]);
    renderDiagnostics({});
    updateCharts({}, []);
    renderQueryError(error);
    setStatus("Error");
  } finally {
    clearQueryLoading();
  }
}

async function hydrateMeta() {
  try {
    const meta = await getMeta();
    renderMetaStrip(meta, {});
  } catch (_error) {
    renderMetaStrip({}, {});
  }
}

function applyTheme(nextTheme) {
  theme = nextTheme === "dark" ? "dark" : "light";
  document.body.setAttribute("data-theme", theme);
  if (themeToggle) {
    themeToggle.textContent = `Theme: ${theme === "dark" ? "Dark" : "Light"}`;
  }
  try {
    window.localStorage.setItem("legacylens-theme", theme);
  } catch (_error) {
    // Ignore storage errors (private mode).
  }
}

function inferGraphSymbol(query, sources = []) {
  const fromSource = (sources || []).find((source) => source.symbol_name)?.symbol_name;
  if (fromSource) {
    return String(fromSource).toUpperCase();
  }

  const tokenMatches = String(query || "").toUpperCase().match(/[A-Z0-9_-]{3,}/g) || [];
  const candidates = tokenMatches.filter((token) => token.includes("_") || token.includes("-"));
  if (candidates.length) {
    return candidates[0];
  }
  return null;
}

function findFallbackSymbol(requestedSymbol, sources = []) {
  const sourceSymbols = Array.from(
    new Set((sources || []).map((source) => source.symbol_name).filter(Boolean).map((name) => String(name).toUpperCase())),
  );
  if (!sourceSymbols.length) {
    return null;
  }
  const normalized = String(requestedSymbol || "").toUpperCase();
  if (!normalized) {
    return sourceSymbols[0];
  }
  const containsMatch = sourceSymbols.find((symbol) => symbol.includes(normalized) || normalized.includes(symbol));
  return containsMatch || sourceSymbols[0];
}

async function runGraphLookup(symbol, options = {}) {
  const normalizedInput = String(symbol || "").trim().toUpperCase();
  if (!normalizedInput) {
    return;
  }
  if (!options.silentStatus) {
    setStatus("Mapping");
  }

  const doLookup = async (lookupSymbol) => {
    await ensureGraphLib();
    const [callersData, graphData] = await Promise.all([getCallers(lookupSymbol), getGraph(lookupSymbol)]);
    return { callersData, graphData, lookupSymbol };
  };

  try {
    let { callersData, graphData, lookupSymbol } = await doLookup(normalizedInput);
    if (options.allowFallback && !(graphData.edges || []).length) {
      const fallback = findFallbackSymbol(normalizedInput, lastSources);
      if (fallback && fallback !== normalizedInput) {
        ({ callersData, graphData, lookupSymbol } = await doLookup(fallback));
      }
    }

    renderCallers(callersData.callers || []);
    renderGraph(graphData);
    const emptyGraph = !(graphData.edges || []).length;
    if (emptyGraph) {
      setGraphEmpty(true, `No dependency links for ${lookupSymbol}. Try full symbol name (example: CBL_OC_DUMP).`);
    } else {
      setGraphEmpty(false);
      symbolInput.value = lookupSymbol;
    }

    const stats = getGraphStats();
    renderGraphStats(stats);
    renderGraphLegend();

    if (!options.silentStatus) {
      setStatus("Ready");
    }
  } catch (error) {
    renderCallers([`Lookup failed: ${String(error)}`]);
    setGraphEmpty(true, `Graph lookup failed for ${normalizedInput}.`);
    if (!options.silentStatus) {
      setStatus("Error");
    }
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

if (clearLogBtn) {
  clearLogBtn.addEventListener("click", () => {
    clearQueryLog();
    renderQueryLog();
  });
}

if (fusionToggle) {
  setFusionEnabled(fusionEnabled);
  fusionToggle.addEventListener("click", () => {
    fusionEnabled = !fusionEnabled;
    setFusionEnabled(fusionEnabled);
  });
}

if (metaToggle) {
  metaToggle.addEventListener("click", () => {
    toggleMetaDetails();
  });
}

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    applyTheme(theme === "light" ? "dark" : "light");
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
setGraphEmpty(true, "Lookup a symbol to render graph topology.");
renderQueryLog();
renderGraphLegend();
hydrateMeta();
{
  let stored = "light";
  try {
    stored = window.localStorage.getItem("legacylens-theme") || "light";
  } catch (_error) {
    stored = "light";
  }
  applyTheme(stored);
}
