import { getCallers, getGraph, getMeta, queryCodebase, queryCodebaseStream } from "./api-client.js?v=20260305f";
import { initCharts, updateCharts } from "./charts.js?v=20260305f";
import { clearGraph, renderGraph, getGraphStats } from "./graph.js?v=20260305f";
import {
  addToQueryLog,
  clearQueryLog,
  clearQueryLoading,
  renderAnswer,
  renderCallers,
  renderDiagnostics,
  renderFallback,
  renderLowConfidence,
  renderResponseLayout,
  renderGraphLegend,
  renderGraphStats,
  renderMetaStrip,
  renderQueryLog,
  renderQueryError,
  renderSources,
  setGraphEmpty,
  setStatus,
  setQueryLoading,
  toggleMetaDetails,
  updateSessionStats,
} from "./ui.js?v=20260305f";

const queryForm = document.getElementById("query-form");
const queryInput = document.getElementById("query-input");
const graphForm = document.getElementById("graph-form");
const symbolInput = document.getElementById("symbol-input");
const chips = document.querySelectorAll(".chip");
const clearLogBtn = document.getElementById("clear-log-btn");
const metaToggle = document.getElementById("meta-toggle");
const themeToggle = document.getElementById("theme-toggle");

let chartLibReady = false;
let graphLibReady = false;
const fusionEnabled = false;
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

function _summarizeAnswerForLog(answer) {
  const compact = String(answer || "").replace(/\s+/g, " ").trim();
  if (!compact) return "No summary generated.";
  return compact.length > 180 ? `${compact.slice(0, 177)}...` : compact;
}

function _evidenceForLog(sources = []) {
  const top = (sources || [])[0];
  if (!top) return "No source lines.";
  const filePath = top.file_path || "unknown";
  const start = Number(top.line_start || 0);
  const end = Number(top.line_end || 0);
  if (start > 0 && end > 0) {
    return `${filePath}:L${start}-${end}`;
  }
  return filePath;
}

function _recordQuery({ diagnostics = {}, sources = [], answer = "", answerId = "-" } = {}) {
  session.queryCount += 1;
  session.similaritySum += Number(diagnostics.top1_score || 0);
  for (const s of sources || []) {
    session.filesSeen.add(s.file_path);
  }
  _updateSessionStats();
  addToQueryLog({
    query: queryInput.value,
    ts: Date.now(),
    topScore: Number(diagnostics.top1_score || 0),
    answerId,
    summary: _summarizeAnswerForLog(answer),
    evidence: _evidenceForLog(sources),
  });
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
  setQueryLoading(query, fusionEnabled);
  renderFallback({ active: false });
  try {
    let renderedGraphSymbol = null;
    const renderContext = async (payload) => {
      const sources = payload.sources || [];
      lastSources = sources;
      renderResponseLayout({
        query,
        diagnostics: payload.diagnostics || {},
        sources,
        queryMeta: payload.query_meta || {},
        fusionEnabled,
        answerId: payload.answer_id || "-",
      });
      renderSources(sources);
      renderDiagnostics(payload.diagnostics || {});
      renderFallback(payload.fallback || { active: false });
      renderMetaStrip({}, payload.query_meta || {});
      updateCharts(payload.diagnostics || {}, sources);

      const inferredSymbol = inferGraphSymbol(query, sources);
      if (inferredSymbol) {
        symbolInput.value = inferredSymbol;
        if (renderedGraphSymbol !== inferredSymbol) {
          renderedGraphSymbol = inferredSymbol;
          await runGraphLookup(inferredSymbol, { allowFallback: true, silentStatus: true });
        }
      } else {
        if (renderedGraphSymbol !== "") {
          renderedGraphSymbol = "";
          clearGraph();
          renderCallers([]);
          renderGraphStats({ nodeCount: 0, edgeCount: 0, edgesByRelation: {} });
          setGraphEmpty(true, "No symbol inferred from this query. Enter one above to map dependencies.");
        }
      }
    };

    let streamedAnswer = "";
    const answerEl = document.getElementById("answer-text");
    if (answerEl) {
      answerEl.textContent = "";
    }
    const payload = await queryCodebaseStream(query, {
      onToken: (event) => {
        const token = typeof event?.token === "string" ? event.token : "";
        if (!token) {
          return;
        }
        streamedAnswer += token;
        renderAnswer(streamedAnswer);
      },
      onContext: (payload) => {
        renderContext(payload).catch(() => {
          // Final payload path still renders if early context processing fails.
        });
      },
    }).catch(async (error) => {
      const fallbackPayload = await queryCodebase(query);
      renderAnswer(fallbackPayload.answer || "");
      return fallbackPayload;
    });
    await ensureChartLib();
    const finalAnswer = payload.answer || streamedAnswer;
    await renderContext(payload);
    if (finalAnswer) {
      renderAnswer(finalAnswer);
    } else {
      renderAnswer("No answer generated.");
    }
    renderLowConfidence(null);
    const sources = payload.sources || [];
    _recordQuery({
      diagnostics: payload.diagnostics || {},
      sources,
      answer: finalAnswer,
      answerId: payload.answer_id || "-",
    });
    setStatus("Ready");
  } catch (error) {
    renderAnswer("Query failed.");
    renderResponseLayout({
      query,
      diagnostics: {},
      sources: [],
      queryMeta: {},
      fusionEnabled,
      answerId: "-",
    });
    renderSources([]);
    renderDiagnostics({});
    renderFallback({ active: false });
    updateCharts({}, []);
    if (error && typeof error.message === "string") {
      try {
        const payload = JSON.parse(error.message);
        renderLowConfidence(payload);
      } catch {
        renderLowConfidence(null);
      }
    }
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

  const fromDependencyLine = (sources || [])
    .map((source) => {
      const text = String(source?.text || "").toUpperCase();
      const dependencyMatch = text.match(/\b(?:PERFORM|CALL)\s+['"]?([A-Z0-9-]{2,})['"]?/);
      if (dependencyMatch?.[1]) {
        return dependencyMatch[1];
      }
      const paragraphMatch = text.match(/^\s*([A-Z0-9][A-Z0-9-]{2,})\.\s*$/m);
      return paragraphMatch?.[1] || null;
    })
    .find(Boolean);
  if (fromDependencyLine) {
    return fromDependencyLine;
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
    clearGraph();
    renderGraphStats({ nodeCount: 0, edgeCount: 0, edgesByRelation: {} });
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

window.addEventListener("legacylens:retry-relaxed", async () => {
  const raw = queryInput.value.trim();
  if (!raw) return;
  await runQuery(`${raw} broader context`);
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
