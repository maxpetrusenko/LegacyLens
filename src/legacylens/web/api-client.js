export async function queryCodebase(query) {
  const res = await fetch("/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw new Error(`Query failed (${res.status})`);
  }
  return res.json();
}

export async function getCallers(symbol) {
  const res = await fetch(`/callers/${encodeURIComponent(symbol)}`);
  if (!res.ok) {
    throw new Error(`Callers lookup failed (${res.status})`);
  }
  return res.json();
}

export async function getGraph(symbol) {
  const res = await fetch(`/graph/${encodeURIComponent(symbol)}`);
  if (!res.ok) {
    throw new Error(`Graph lookup failed (${res.status})`);
  }
  return res.json();
}
