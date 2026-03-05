async function _parseResponse(res) {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (typeof err.detail === "string") {
        msg = err.detail;
      } else if (err.detail && typeof err.detail === "object") {
        msg = JSON.stringify(err.detail);
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

export function parseSSEChunks(input, previousRemainder = "") {
  const text = `${previousRemainder}${input}`;
  const frames = text.split("\n\n");
  const remainder = frames.pop() || "";
  const events = [];
  for (const frame of frames) {
    const lines = frame.split("\n");
    let event = "message";
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (!dataLines.length) {
      continue;
    }
    const raw = dataLines.join("\n");
    let data = raw;
    try {
      data = JSON.parse(raw);
    } catch {
      data = raw;
    }
    events.push({ event, data });
  }
  return { events, remainder };
}

export async function queryCodebase(query) {
  const res = await fetch("/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return _parseResponse(res);
}

export async function queryCodebaseStream(
  query,
  { onToken = () => {}, onContext = () => {}, onDone = () => {}, onError = () => {} } = {},
) {
  const res = await fetch("/query/stream", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    return _parseResponse(res);
  }
  if (!res.body) {
    throw new Error("Streaming response body missing.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let remainder = "";
  let finalPayload = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    const chunk = decoder.decode(value, { stream: true });
    const parsed = parseSSEChunks(chunk, remainder);
    remainder = parsed.remainder;
    for (const event of parsed.events) {
      if (event.event === "token") {
        onToken(event.data);
      } else if (event.event === "context") {
        onContext(event.data);
      } else if (event.event === "done") {
        finalPayload = event.data;
        onDone(event.data);
      } else if (event.event === "error") {
        onError(event.data);
        throw new Error(event.data?.error || "Stream error");
      }
    }
  }

  if (remainder.trim()) {
    const parsed = parseSSEChunks("", remainder);
    for (const event of parsed.events) {
      if (event.event === "done") {
        finalPayload = event.data;
      }
    }
  }
  if (!finalPayload) {
    throw new Error("Stream ended without done event.");
  }
  return finalPayload;
}

export async function getCallers(symbol) {
  const res = await fetch(`/callers/${encodeURIComponent(symbol)}`);
  return _parseResponse(res);
}

export async function getGraph(symbol) {
  const res = await fetch(`/graph/${encodeURIComponent(symbol)}`);
  return _parseResponse(res);
}

export async function getMeta() {
  const res = await fetch("/meta");
  return _parseResponse(res);
}
