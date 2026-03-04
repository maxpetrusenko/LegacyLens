function byId(id) {
  return document.getElementById(id);
}

export const el = {
  status: byId("status-badge"),
  answer: byId("answer-text"),
  queryError: byId("query-error"),
  sourcesList: byId("sources-list"),
  sourcesEmpty: byId("sources-empty"),
  graphEmpty: byId("graph-empty"),
  callersList: byId("callers-list"),
  statLatency: byId("stat-latency"),
  statTop1: byId("stat-top1"),
  statHybrid: byId("stat-hybrid"),
  statHits: byId("stat-hits"),
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

export function setStatus(label) {
  el.status.textContent = label;
}

export function setQueryLoading() {
  setStatus("Searching");
  el.queryError.textContent = "";
  el.answer.textContent = "";
  el.answer.classList.add("skeleton");
}

export function clearQueryLoading() {
  el.answer.classList.remove("skeleton");
}

export function renderAnswer(text) {
  el.answer.textContent = text || "No answer generated.";
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

function _renderScoreBar(score) {
  const pct = Math.round(Number(score || 0) * 100);
  return `
    <div class="score-bar-wrap">
      <div class="score-bar-fill" style="width: ${pct}%"></div>
      <span class="score-label">${pct}%</span>
    </div>
  `;
}

function _renderTags(source) {
  const tags = [];
  if (source.division) tags.push(source.division);
  if (source.section) tags.push(source.section);
  if (source.symbol_name) tags.push(source.symbol_name);
  if (Array.isArray(source.tags)) tags.push(...source.tags.slice(0, 2));
  if (!tags.length) {
    return "";
  }
  return tags.map((t) => `<span class="source-tag">${_escapeHtml(String(t))}</span>`).join(" ");
}

function _renderSourceHeader(source, key, isExpanded) {
  const citation = source.citation || `${source.file_path || "unknown"}:${source.line_start || 1}-${source.line_end || 1}`;
  const tagsMarkup = _renderTags(source);
  return `
    <div class="source-header">
      <div class="source-meta">
        <span class="source-path">${_escapeHtml(citation)}</span>
        ${tagsMarkup ? `<div class="source-tags">${tagsMarkup}</div>` : ""}
      </div>
      <div class="source-actions">
        ${_renderScoreBar(source.score)}
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

    _attachSourceListeners(li);
  }

  _applyPrism(el.sourcesList);
}

export function renderDiagnostics(d = {}) {
  el.statLatency.textContent = `${Number(d.latency_ms || 0)} ms`;
  el.statTop1.textContent = Number(d.top1_score || 0).toFixed(4);
  el.statHybrid.textContent = d.hybrid_triggered ? "Yes" : "No";
  el.statHits.textContent = `${Number(d.semantic_hits || 0)}/${Number(d.fallback_hits || 0)}`;
}

export function renderQueryError(error) {
  el.queryError.textContent = String(error);
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

export function setGraphEmpty(isEmpty) {
  el.graphEmpty.style.display = isEmpty ? "block" : "none";
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
    li.innerHTML = `
      <span class="query-log-q">${_escapeHtml(entry.query)}</span>
      <span class="query-log-time">${new Date(entry.ts).toLocaleTimeString()}</span>
    `;
    container.appendChild(li);
  }
}

export function renderKpiChips(diagnostics = {}, sources = [], containerId = "kpi-chips") {
  const container = byId(containerId);
  if (!container) return;

  const chips = [
    { label: "Retrieved", value: String(diagnostics.chunks_returned ?? sources.length) },
    { label: "Latency", value: `${Number(diagnostics.latency_ms || 0)}ms` },
    { label: "Top Score", value: Number(diagnostics.top1_score || 0).toFixed(3) },
    { label: "Files", value: String(new Set(sources.map(s => s.file_path)).size) },
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
