async function _parseResponse(res) {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (typeof err.detail === "string") {
        msg = err.detail;
      } else if (err.detail && typeof err.detail === "object") {
        msg = err.detail.error || err.detail.cause || JSON.stringify(err.detail);
      } else if (typeof err.message === "string") {
        msg = err.message;
      }
    } catch {
      // Keep generic message when response body is not JSON.
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function queryCodebase(query) {
  const res = await fetch("/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return _parseResponse(res);
}

export async function getCallers(symbol) {
  const res = await fetch(`/callers/${encodeURIComponent(symbol)}`);
  return _parseResponse(res);
}

export async function getGraph(symbol) {
  const res = await fetch(`/graph/${encodeURIComponent(symbol)}`);
  return _parseResponse(res);
}
