function byId(id) {
  return document.getElementById(id);
}

export const el = {
  status: byId("status-badge"),
  answer: byId("answer-text"),
  answerModelMeta: byId("answer-model-meta"),
  answerId: byId("answer-id"),
  copyAnswerId: byId("copy-answer-id"),
  queryError: byId("query-error"),
  generating: byId("generating-indicator"),
  fallbackBanner: byId("fallback-banner"),
  fallbackText: byId("fallback-text"),
  fallbackDismiss: byId("fallback-dismiss"),
  lowConfidence: byId("low-confidence"),
  lowConfidenceList: byId("low-confidence-list"),
  lowConfidenceRetry: byId("low-confidence-retry"),
  sourcesList: byId("sources-list"),
  sourcesTitle: byId("sources-title"),
  sourcesEmpty: byId("sources-empty"),
  graphEmpty: byId("graph-empty"),
  callersList: byId("callers-list"),
  statLatency: byId("stat-latency"),
  statTop1: byId("stat-top1"),
  statHybrid: byId("stat-hybrid"),
  statHits: byId("stat-hits"),
  graphStats: byId("graph-stats"),
  graphLegend: byId("graph-legend"),
  kpiChips: byId("kpi-chips"),
  sessionStats: byId("session-stats"),
  logEntries: byId("log-entries"),
  clearLogBtn: byId("clear-log-btn"),
  fusionToggle: byId("fusion-toggle"),
  metaToggle: byId("meta-toggle"),
  metaDetails: byId("meta-details"),
  datasetLabel: byId("dataset-label"),
  datasetList: byId("dataset-list"),
  metaDataset: byId("meta-dataset"),
  metaVectors: byId("meta-vectors"),
  metaDims: byId("meta-dims"),
  metaMetric: byId("meta-metric"),
  metaModel: byId("meta-model"),
  metaLlm: byId("meta-llm"),
  metaEmbedProvider: byId("meta-embed-provider"),
  metaCollection: byId("meta-collection"),
};

const _expandState = new Map();
const _queryLog = [];

export function getExpandState(key) {
  return _expandState.get(key) ?? false;
}

export function setExpandState(key, expanded) {
  _expandState.set(key, expanded);
}

export function toggleExpand(key) {
  const current = getExpandState(key);
  setExpandState(key, !current);
  return !current;
}

export function getQueryLog() {
  return [..._queryLog];
}

export function addToQueryLog(entry) {
  _queryLog.unshift(entry);
  if (_queryLog.length > 50) _queryLog.pop();
}

export function clearQueryLog() {
  _queryLog.splice(0, _queryLog.length);
}

export function setStatus(label) {
  el.status.textContent = label;
}

export function setGenerating(active) {
  if (!el.generating) return;
  el.generating.style.display = active ? "inline-flex" : "none";
}

function _formatPercent(score, digits = 1) {
  return `${(Number(score || 0) * 100).toFixed(digits)}%`;
}

function _uniqueDivisions(sources = []) {
  return Array.from(new Set((sources || []).map((source) => source.division).filter(Boolean)));
}

function _divisionSummary(sources = []) {
  const divisions = _uniqueDivisions(sources);
  if (!divisions.length) return "Unknown";
  if (divisions.length <= 2) return divisions.join(", ");
  return `${divisions.slice(0, 2).join(", ")} +${divisions.length - 2}`;
}

function _lineRange(source = {}) {
  const start = source.line_start;
  const end = source.line_end;
  if (typeof start === "number" && typeof end === "number") {
    return `L${start}-${end}`;
  }
  return "L?-?";
}

export function setQueryLoading(query = "", fusionEnabled = false) {
  setStatus("Searching");
  el.queryError.textContent = "";
  el.answer.textContent = "";
  renderResponseLayout({
    query,
    answerId: "pending",
    diagnostics: {},
    sources: [],
    queryMeta: {},
    fusionEnabled,
  });
  renderLowConfidence(null);
  el.answer.classList.add("skeleton");
  setGenerating(true);
}

export function clearQueryLoading() {
  el.answer.classList.remove("skeleton");
  setGenerating(false);
}

export function renderAnswer(text) {
  el.answer.textContent = text || "No answer generated.";
}

export function renderResponseLayout({
  sources = [],
  queryMeta = {},
  answerId = "-",
} = {}) {
  if (el.answerModelMeta) {
    const model = queryMeta.llm_model || "Model unavailable";
    el.answerModelMeta.textContent = model;
  }
  if (el.answerId) {
    el.answerId.textContent = answerId || "-";
  }
  if (el.sourcesTitle) {
    el.sourcesTitle.textContent = `Source Code (${Number(sources.length || 0)} matches)`;
  }
}

function _sourceKey(source) {
  if (source.file_path && source.line_start && source.line_end) {
    return `${source.file_path}:${source.line_start}-${source.line_end}`;
  }
  if (source.citation) {
    return source.citation;
  }
  return `${source.text || ""}`.slice(0, 120);
}

function _renderTags(source) {
  const tags = [];
  if (source.division) tags.push(source.division);
  if (source.section) tags.push(source.section);
  if (source.symbol_name) tags.push(source.symbol_name);
  if (Array.isArray(source.tags)) tags.push(...source.tags.slice(0, 2));
  const uniqueTags = Array.from(new Set(tags.map((tag) => String(tag).trim()).filter(Boolean)));
  if (!uniqueTags.length) {
    return "";
  }
  return uniqueTags.map((t) => `<span class="source-tag">${_escapeHtml(t)}</span>`).join(" ");
}

function _renderSourceHeader(source, key, isExpanded) {
  const filePath = source.file_path || source.citation || "unknown";
  const lineRange = _lineRange(source);
  const score = _formatPercent(source.score, 1);
  const division = source.division || "Unknown";
  const tagsMarkup = _renderTags(source);
  const previewLine = String(source.text || "")
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean) || "No preview line available.";
  return `
    <div class="source-header">
      <div class="source-meta">
        <span class="source-path">${_escapeHtml(filePath)}</span>
        <span class="source-context">${_escapeHtml(lineRange)} · ${_escapeHtml(division)}</span>
        <span class="source-preview">${_escapeHtml(previewLine)}</span>
        ${tagsMarkup ? `<div class="source-tags">${tagsMarkup}</div>` : ""}
      </div>
      <div class="source-actions">
        <span class="source-score">${score}</span>
        <button class="source-action-btn expand-btn" data-key="${key}">
          ${isExpanded ? "Collapse" : "Expand"}
        </button>
        <button class="source-action-btn copy-btn" data-key="${key}">Copy</button>
      </div>
    </div>
  `;
}

function _renderSourceBody(source, key) {
  return `
    <div class="source-body" data-key="${key}">
      <pre class="source-code"><code class="language-cobol">${_escapeHtml(source.text || "")}</code></pre>
    </div>
  `;
}

function _escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function _applyPrism(element) {
  if (window.Prism) {
    Prism.highlightAllUnder(element);
  }
}

function _attachSourceListeners(li) {
  const expandBtn = li.querySelector(".expand-btn");
  const copyBtn = li.querySelector(".copy-btn");
  const body = li.querySelector(".source-body");

  expandBtn.addEventListener("click", () => {
    const key = expandBtn.dataset.key;
    const isExpanded = toggleExpand(key);
    body.classList.toggle("is-collapsed", !isExpanded);
    li.classList.toggle("is-collapsed", !isExpanded);
    expandBtn.textContent = isExpanded ? "Collapse" : "Expand";
  });

  copyBtn.addEventListener("click", async () => {
    const code = li.querySelector("code")?.textContent || "";
    try {
      await navigator.clipboard.writeText(code);
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
    } catch {}
  });
}

export function renderSources(sources = []) {
  el.sourcesList.innerHTML = "";
  if (el.sourcesList) {
    el.sourcesList.scrollTop = 0;
  }
  if (el.sourcesTitle) {
    el.sourcesTitle.textContent = `Source Code (${Number(sources.length || 0)} matches)`;
  }
  if (!sources.length) {
    el.sourcesEmpty.style.display = "block";
    return;
  }
  el.sourcesEmpty.style.display = "none";

  for (let i = 0; i < sources.length; i++) {
    const source = sources[i];
    const key = _sourceKey(source);
    const isExpanded = i === 0 || getExpandState(key);
    if (i === 0) setExpandState(key, true);

    const li = document.createElement("li");
    li.className = "source-item";
    li.innerHTML = `
      ${_renderSourceHeader(source, key, isExpanded)}
      ${_renderSourceBody(source, key)}
    `;
    el.sourcesList.appendChild(li);

    const body = li.querySelector(".source-body");
    body.classList.toggle("is-collapsed", !isExpanded);
    li.classList.toggle("is-collapsed", !isExpanded);

    _attachSourceListeners(li);
  }

  _applyPrism(el.sourcesList);
}

export function renderDiagnostics(d = {}) {
  el.statLatency.textContent = `${Number(d.latency_ms || 0)} ms`;
  el.statTop1.textContent = _formatPercent(d.top1_score, 1);
  el.statHybrid.textContent = d.hybrid_triggered ? "Yes" : "No";
  el.statHits.textContent = `${Number(d.semantic_hits || 0)}/${Number(d.fallback_hits || 0)}`;
}

function _fallbackMessage(fallback) {
  const reason = fallback?.reason || "unknown";
  if (fallback?.mode === "keyword") {
    return `Keyword fallback active (${reason}). Results may be less semantically precise.`;
  }
  if (fallback?.mode === "citations_only") {
    return `Citations-only fallback active (${reason}). No synthesized prose returned.`;
  }
  return `Fallback active (${reason}).`;
}

export function renderFallback(fallback) {
  if (!el.fallbackBanner || !el.fallbackText) return;
  if (!fallback?.active) {
    el.fallbackBanner.style.display = "none";
    el.fallbackText.textContent = "";
    return;
  }
  el.fallbackBanner.classList.remove("is-info", "is-error");
  el.fallbackBanner.classList.add(fallback.severity === "error" ? "is-error" : "is-info");
  el.fallbackText.textContent = _fallbackMessage(fallback);
  el.fallbackBanner.style.display = "flex";
}

if (el.fallbackDismiss) {
  el.fallbackDismiss.addEventListener("click", () => {
    if (el.fallbackBanner) {
      el.fallbackBanner.style.display = "none";
    }
  });
}

if (el.copyAnswerId) {
  el.copyAnswerId.addEventListener("click", async () => {
    const value = el.answerId?.textContent || "";
    try {
      await navigator.clipboard.writeText(value);
      el.copyAnswerId.textContent = "Copied";
      setTimeout(() => {
        if (el.copyAnswerId) {
          el.copyAnswerId.textContent = "Copy ID";
        }
      }, 1200);
    } catch {}
  });
}

export function renderLowConfidence(detail) {
  if (!el.lowConfidence || !el.lowConfidenceList) return;
  if (!detail || !Array.isArray(detail.suggestions) || !detail.suggestions.length) {
    el.lowConfidence.style.display = "none";
    el.lowConfidenceList.innerHTML = "";
    return;
  }
  el.lowConfidenceList.innerHTML = detail.suggestions
    .map((item) => `<li>${_escapeHtml(String(item))}</li>`)
    .join("");
  el.lowConfidence.style.display = "block";
}

if (el.lowConfidenceRetry) {
  el.lowConfidenceRetry.addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("legacylens:retry-relaxed"));
  });
}

export function renderQueryError(error) {
  if (error && typeof error === "object") {
    if (typeof error.error === "string") {
      const action = typeof error.action === "string" ? ` ${error.action}` : "";
      el.queryError.textContent = `${error.error}.${action}`.trim();
      return;
    }
    if (typeof error.message === "string") {
      el.queryError.textContent = String(error.message);
      return;
    }
  }
  el.queryError.textContent = String(error || "");
}

export function renderCallers(callers = []) {
  el.callersList.innerHTML = "";
  if (!callers.length) {
    const li = document.createElement("li");
    li.textContent = "No callers found.";
    el.callersList.appendChild(li);
    return;
  }
  for (const caller of callers) {
    const li = document.createElement("li");
    li.textContent = caller;
    el.callersList.appendChild(li);
  }
}

export function setGraphEmpty(isEmpty, message = null) {
  if (el.graphEmpty) {
    if (message) {
      el.graphEmpty.textContent = message;
    } else if (!el.graphEmpty.textContent.trim()) {
      el.graphEmpty.textContent = "Lookup a symbol to render graph topology.";
    }
    el.graphEmpty.style.display = isEmpty ? "block" : "none";
  }
}

export function renderQueryLog(containerId = "log-entries") {
  const container = byId(containerId) || byId("query-log-list");
  if (!container) return;
  container.innerHTML = "";
  if (!_queryLog.length) {
    container.innerHTML = '<li class="query-log-empty">No queries yet.</li>';
    return;
  }
  for (const entry of _queryLog) {
    const li = document.createElement("li");
    li.className = "query-log-item";
    const stats = typeof entry.topScore === "number" ? `Top ${(entry.topScore * 100).toFixed(1)}%` : "Top -";
    const summary = entry.summary || "No summary captured.";
    const evidence = entry.evidence || "No line evidence captured.";
    const answerId = entry.answerId || "-";
    const answerIdAttr = String(answerId).replace(/"/g, "&quot;");
    li.innerHTML = `
      <div class="query-log-main">
        <span class="query-log-q">${_escapeHtml(entry.query)}</span>
        <span class="query-log-time">${new Date(entry.ts).toLocaleTimeString()}</span>
      </div>
      <div class="query-log-meta">
        <code class="query-log-id">${_escapeHtml(answerId)}</code>
        <button type="button" class="source-action-btn query-log-copy" data-answer-id="${answerIdAttr}">Copy ID</button>
        <span class="query-log-top">${_escapeHtml(stats)}</span>
      </div>
      <p class="query-log-summary">${_escapeHtml(summary)}</p>
      <p class="query-log-lines">${_escapeHtml(evidence)}</p>
    `;
    container.appendChild(li);
  }
  const copyButtons = container.querySelectorAll(".query-log-copy");
  for (const button of copyButtons) {
    button.addEventListener("click", async () => {
      const value = button.getAttribute("data-answer-id") || "";
      try {
        await navigator.clipboard.writeText(value);
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = "Copy ID";
        }, 1200);
      } catch {}
    });
  }
}

export function renderKpiChips(diagnostics = {}, sources = [], options = {}) {
  const { containerId = "kpi-chips", fusionEnabled = false } = options;
  const container = byId(containerId);
  if (!container) return;
  const retrieved = Number(sources.length || 0);
  const filesHit = new Set((sources || []).map((source) => source.file_path).filter(Boolean)).size;

  const chips = [
    { label: "Search", value: fusionEnabled ? "Fusion ON" : "Fusion OFF" },
    { label: "Retrieved", value: `${retrieved} chunks` },
    { label: "Latency", value: `${Number(diagnostics.latency_ms || 0)}ms` },
    { label: "Top score", value: _formatPercent(diagnostics.top1_score, 1) },
    { label: "Files hit", value: String(filesHit) },
    { label: "Divisions", value: _divisionSummary(sources) },
  ];

  container.innerHTML = chips
    .map(c => `<span class="kpi-chip"><span class="kpi-label">${c.label}</span> ${c.value}</span>`)
    .join("");
}

export function updateSessionStats(stats) {
  const container = byId("session-stats");
  if (!container) return;
  container.innerHTML = `
    <span class="session-stat">${stats.queryCount ?? 0} queries</span>
    <span class="session-stat">Avg similarity: ${Number(stats.avgSimilarity ?? 0).toFixed(3)}</span>
    <span class="session-stat">${stats.filesSeen ?? 0} files seen</span>
  `;
}

export function renderGraphStats(stats = {}) {
  if (!el.graphStats) {
    return;
  }
  const { nodeCount = 0, edgeCount = 0 } = stats;
  el.graphStats.innerHTML = `
    <span class="graph-stat">${nodeCount} nodes</span>
    <span class="graph-stat">${edgeCount} edges</span>
  `;
}

export function renderGraphLegend() {
  if (!el.graphLegend) {
    return;
  }
  el.graphLegend.innerHTML = `
    <div class="legend-item">
      <span class="legend-dot legend-perform"></span>
      <span>PERFORM</span>
    </div>
    <div class="legend-item">
      <span class="legend-dot legend-call"></span>
      <span>CALL</span>
    </div>
    <div class="legend-item">
      <span class="legend-dot legend-unknown"></span>
      <span>Unknown</span>
    </div>
  `;
}

export function renderMetaStrip(meta = {}, queryMeta = {}) {
  const vectorCount = Number.isFinite(Number(meta.vector_count)) ? Number(meta.vector_count) : null;
  const dataset = meta.default_codebase ? String(meta.default_codebase).split("/").pop() : "-";
  const hasDataset = Boolean(dataset && dataset !== "-" && vectorCount !== null && vectorCount > 0);

  if (el.datasetLabel) {
    el.datasetLabel.textContent = hasDataset ? dataset : "None loaded";
  }
  if (el.datasetList) {
    if (hasDataset) {
      el.datasetList.innerHTML = `<span class="dataset-chip">${_escapeHtml(dataset)} · ${vectorCount} vectors</span>`;
    } else {
      el.datasetList.innerHTML = '<span class="strip-empty">No datasets indexed yet.</span>';
    }
  }
  if (el.metaDataset) {
    el.metaDataset.textContent = dataset || "-";
  }
  if (el.metaVectors) {
    el.metaVectors.textContent = `Vectors: ${meta.vector_count ?? "-"}`;
  }
  if (el.metaDims) {
    el.metaDims.textContent = `Dims: ${meta.vector_dim ?? "-"}`;
  }
  if (el.metaMetric) {
    el.metaMetric.textContent = `Metric: ${meta.vector_metric ?? "-"}`;
  }
  if (el.metaModel) {
    const model = queryMeta.embed_model || meta.embed_model || "-";
    el.metaModel.textContent = `Model: ${model}`;
  }
  if (el.metaLlm) {
    el.metaLlm.textContent = `LLM: ${queryMeta.llm_model || meta.llm_model || "-"}`;
  }
  if (el.metaEmbedProvider) {
    el.metaEmbedProvider.textContent = `Embed: ${queryMeta.embed_provider || meta.embed_provider || "-"}`;
  }
  if (el.metaCollection) {
    el.metaCollection.textContent = `Collection: ${queryMeta.qdrant_collection || meta.qdrant_collection || "-"}`;
  }
}

export function setFusionEnabled(enabled) {
  if (!el.fusionToggle) return;
  el.fusionToggle.setAttribute("aria-pressed", enabled ? "true" : "false");
  el.fusionToggle.classList.toggle("is-on", enabled);
  el.fusionToggle.textContent = enabled ? "Fusion ON" : "Fusion OFF";
}

export function toggleMetaDetails() {
  if (!el.metaToggle || !el.metaDetails) {
    return;
  }
  const expanded = el.metaToggle.getAttribute("aria-expanded") === "true";
  const next = !expanded;
  el.metaToggle.setAttribute("aria-expanded", next ? "true" : "false");
  el.metaDetails.classList.toggle("is-hidden", !next);
}
