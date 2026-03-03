const queryForm = document.getElementById("query-form");
const callersForm = document.getElementById("callers-form");
const queryInput = document.getElementById("query-input");
const symbolInput = document.getElementById("symbol-input");
const answerText = document.getElementById("answer-text");
const sourcesList = document.getElementById("sources-list");
const callersList = document.getElementById("callers-list");
const statusBadge = document.getElementById("status-badge");
const diagError = document.getElementById("diag-error");
const diagList = document.getElementById("diag-list");

function setStatus(label) {
  statusBadge.textContent = label;
}

function setDiag(key, value) {
  const map = {
    latency_ms: "Latency",
    top1_score: "Top1 Score",
    hybrid_triggered: "Hybrid",
    semantic_hits: "Semantic Hits",
    fallback_hits: "Fallback Hits",
  };
  for (const row of diagList.querySelectorAll("div")) {
    if (row.firstElementChild.textContent === map[key]) {
      row.lastElementChild.textContent = String(value);
    }
  }
}

async function runQuery(question) {
  setStatus("Searching");
  diagError.textContent = "";
  sourcesList.innerHTML = "";
  answerText.textContent = "Loading...";
  try {
    const res = await fetch("/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query: question }),
    });
    const payload = await res.json();
    answerText.textContent = payload.answer ?? "No answer.";
    for (const source of payload.sources ?? []) {
      const li = document.createElement("li");
      li.textContent = `${source.citation} (score: ${Number(source.score).toFixed(4)})`;
      sourcesList.appendChild(li);
    }
    const d = payload.diagnostics ?? {};
    setDiag("latency_ms", d.latency_ms ?? "-");
    setDiag("top1_score", d.top1_score ?? "-");
    setDiag("hybrid_triggered", d.hybrid_triggered ?? "-");
    setDiag("semantic_hits", d.semantic_hits ?? "-");
    setDiag("fallback_hits", d.fallback_hits ?? "-");
    diagError.textContent = d.retrieval_error || "";
    setStatus("Done");
  } catch (error) {
    answerText.textContent = "Query failed.";
    diagError.textContent = String(error);
    setStatus("Error");
  }
}

async function lookupCallers(symbol) {
  callersList.innerHTML = "";
  try {
    const res = await fetch(`/callers/${encodeURIComponent(symbol)}`);
    const payload = await res.json();
    const callers = payload.callers ?? [];
    if (!callers.length) {
      const li = document.createElement("li");
      li.textContent = "No callers found.";
      callersList.appendChild(li);
      return;
    }
    for (const caller of callers) {
      const li = document.createElement("li");
      li.textContent = caller;
      callersList.appendChild(li);
    }
  } catch (error) {
    const li = document.createElement("li");
    li.textContent = `Lookup failed: ${String(error)}`;
    callersList.appendChild(li);
  }
}

queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runQuery(queryInput.value.trim());
});

callersForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await lookupCallers(symbolInput.value.trim());
});

for (const chip of document.querySelectorAll(".chip")) {
  chip.addEventListener("click", async () => {
    const q = chip.dataset.q;
    queryInput.value = q;
    await runQuery(q);
  });
}
