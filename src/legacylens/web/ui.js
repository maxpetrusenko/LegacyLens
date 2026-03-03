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

export function renderSources(sources = []) {
  el.sourcesList.innerHTML = "";
  if (!sources.length) {
    el.sourcesEmpty.style.display = "block";
    return;
  }
  el.sourcesEmpty.style.display = "none";
  for (const source of sources) {
    const li = document.createElement("li");
    const score = Number(source.score || 0).toFixed(4);
    li.textContent = `${source.citation} | score: ${score}`;
    el.sourcesList.appendChild(li);
  }
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
