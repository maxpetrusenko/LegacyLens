let hitsChart;
let scoreChart;
let similarityChart;
let divisionChart;
let chunkTypeChart;

const THEME = {
  accent: "#3fd2ff",
  accent2: "#44f2c8",
  muted: "#2a3f67",
  text: "#bdd1f2",
  grid: "rgba(120,150,196,0.15)",
  tick: "#9fb6db",
};

const PIE_COLORS = ["#44f2c8", "#3fd2ff", "#6b9fff", "#f2a87b", "#ff7aa2", "#4f77b0"];

function baseOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: THEME.text, font: { size: 11 } } },
    },
    scales: {
      x: { ticks: { color: THEME.tick }, grid: { color: THEME.grid } },
      y: { ticks: { color: THEME.tick }, grid: { color: THEME.grid } },
    },
  };
}

function safeGet(id) {
  const el = typeof document === "undefined" ? null : document.getElementById(id);
  return el && typeof window.Chart !== "undefined" ? el : null;
}

function createBarChart(ctx, label, data, colors) {
  return new window.Chart(ctx, {
    type: "bar",
    data: {
      labels: label,
      datasets: [{
        label: "Count",
        data,
        backgroundColor: colors,
        borderRadius: 8,
      }],
    },
    options: baseOptions(),
  });
}

function createDoughnutChart(ctx, labels, data, colors) {
  return new window.Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderColor: "#101d36",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: THEME.text, font: { size: 11 }, padding: 10 },
        },
      },
    },
  });
}

export function initCharts() {
  if (hitsChart || scoreChart) {
    return;
  }

  const hitsCtx = safeGet("hits-chart");
  const scoreCtx = safeGet("score-chart");
  if (hitsCtx) {
    hitsChart = createBarChart(
      hitsCtx,
      ["Semantic", "Fallback"],
      [0, 0],
      [THEME.accent, THEME.accent2]
    );
  }

  if (scoreCtx) {
    scoreChart = createDoughnutChart(
      scoreCtx,
      [">0.8", "0.5-0.8", "<0.5"],
      [0, 0, 1],
      [THEME.accent2, THEME.accent, THEME.muted]
    );
  }

  const simCtx = safeGet("similarity-chart");
  if (simCtx) {
    similarityChart = createBarChart(
      simCtx,
      [],
      [],
      Array(20).fill(THEME.accent)
    );
  }

  const divCtx = safeGet("division-chart");
  if (divCtx) {
    divisionChart = createDoughnutChart(
      divCtx,
      [],
      [],
      PIE_COLORS
    );
  }

  const chunkCtx = safeGet("chunk-type-chart");
  if (chunkCtx) {
    chunkTypeChart = createDoughnutChart(
      chunkCtx,
      [],
      [],
      PIE_COLORS
    );
  }
}

function updateSimilarityChart(sources = []) {
  if (!similarityChart) {
    return;
  }

  const scored = sources
    .map((s) => Number(s.score || 0))
    .filter((s) => s > 0)
    .sort((a, b) => b - a)
    .slice(0, 20);

  if (!scored.length) {
    similarityChart.data.labels = [];
    similarityChart.data.datasets[0].data = [];
    similarityChart.update();
    return;
  }

  similarityChart.data.labels = scored.map((_, i) => `#${i + 1}`);
  similarityChart.data.datasets[0].data = scored;
  const colors = scored.map((s) =>
    s > 0.8 ? THEME.accent2 : s > 0.5 ? THEME.accent : THEME.muted
  );
  similarityChart.data.datasets[0].backgroundColor = colors;
  similarityChart.update();
}

function updateDivisionChart(sources = []) {
  if (!divisionChart) {
    return;
  }

  const counts = {};
  for (const source of sources) {
    const key = String(source.division || "unknown");
    counts[key] = (counts[key] || 0) + 1;
  }
  const entries = Object.entries(counts);
  divisionChart.data.labels = entries.map(([label]) => label);
  divisionChart.data.datasets[0].data = entries.map(([, value]) => value);
  divisionChart.data.datasets[0].backgroundColor = entries.map((_, index) => PIE_COLORS[index % PIE_COLORS.length]);
  divisionChart.update();
}

function _normalizeChunkType(source) {
  const raw = String(source.symbol_type || source.chunk_type || "unknown").toLowerCase();
  if (raw.includes("paragraph")) {
    return "paragraph";
  }
  if (raw.includes("fallback")) {
    return "fallback";
  }
  return raw || "unknown";
}

function updateChunkTypeChart(sources = []) {
  if (!chunkTypeChart) {
    return;
  }

  const counts = {};
  for (const source of sources) {
    const key = _normalizeChunkType(source);
    counts[key] = (counts[key] || 0) + 1;
  }
  const entries = Object.entries(counts);
  chunkTypeChart.data.labels = entries.map(([label]) => label);
  chunkTypeChart.data.datasets[0].data = entries.map(([, value]) => value);
  chunkTypeChart.data.datasets[0].backgroundColor = entries.map((_, index) => PIE_COLORS[index % PIE_COLORS.length]);
  chunkTypeChart.update();
}

export function updateCharts(diagnostics = {}, sources = null) {
  if (hitsChart) {
    const semantic = Number(diagnostics.semantic_hits || 0);
    const fallback = Number(diagnostics.fallback_hits || 0);
    hitsChart.data.datasets[0].data = [semantic, fallback];
    hitsChart.update();
  }

  if (scoreChart) {
    const score = Number(diagnostics.top1_score || 0);
    const bands = [0, 0, 0];
    if (score > 0.8) {
      bands[0] = 1;
    } else if (score >= 0.5) {
      bands[1] = 1;
    } else {
      bands[2] = 1;
    }
    scoreChart.data.datasets[0].data = bands;
    scoreChart.update();
  }

  const sourceList = Array.isArray(sources) ? sources : [];
  updateSimilarityChart(sourceList);
  updateDivisionChart(sourceList);
  updateChunkTypeChart(sourceList);
}
