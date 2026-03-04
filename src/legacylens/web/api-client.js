async function buildHttpError(res, label) {
  let detailText = "";
  try {
    const payload = await res.json();
    if (typeof payload?.detail === "string") {
      detailText = payload.detail;
    } else if (payload?.detail && typeof payload.detail === "object") {
      const parts = [];
      if (payload.detail.error) {
        parts.push(String(payload.detail.error));
      }
      if (payload.detail.cause) {
        parts.push(`cause: ${payload.detail.cause}`);
      }
      if (payload.detail.action) {
        parts.push(`action: ${payload.detail.action}`);
      }
      detailText = parts.join(" | ");
    } else if (payload?.error) {
      detailText = String(payload.error);
    }
  } catch (_error) {
    // Non-JSON response; keep status-only message.
  }
  const suffix = detailText ? `: ${detailText}` : "";
  return new Error(`${label} (${res.status})${suffix}`);
}

export async function queryCodebase(query) {
  const res = await fetch("/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw await buildHttpError(res, "Query failed");
  }
  return res.json();
}

export async function getCallers(symbol) {
  const res = await fetch(`/callers/${encodeURIComponent(symbol)}`);
  if (!res.ok) {
    throw await buildHttpError(res, "Callers lookup failed");
  }
  return res.json();
}

export async function getGraph(symbol) {
  const res = await fetch(`/graph/${encodeURIComponent(symbol)}`);
  if (!res.ok) {
    throw await buildHttpError(res, "Graph lookup failed");
  }
  return res.json();
}
