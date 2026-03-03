let hitsChart;
let scoreChart;

function baseOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#bdd1f2" } },
    },
    scales: {
      x: { ticks: { color: "#9fb6db" }, grid: { color: "rgba(120,150,196,0.15)" } },
      y: { ticks: { color: "#9fb6db" }, grid: { color: "rgba(120,150,196,0.15)" } },
    },
  };
}

export function initCharts() {
  if (hitsChart || scoreChart) {
    return;
  }
  const hitsCtx = document.getElementById("hits-chart");
  const scoreCtx = document.getElementById("score-chart");
  if (!hitsCtx || !scoreCtx || typeof window.Chart === "undefined") {
    return;
  }

  hitsChart = new window.Chart(hitsCtx, {
    type: "bar",
    data: {
      labels: ["Semantic", "Fallback"],
      datasets: [{
        label: "Hits",
        data: [0, 0],
        backgroundColor: ["#3fd2ff", "#44f2c8"],
        borderRadius: 8,
      }],
    },
    options: baseOptions(),
  });

  scoreChart = new window.Chart(scoreCtx, {
    type: "doughnut",
    data: {
      labels: [">0.8", "0.5-0.8", "<0.5"],
      datasets: [{
        data: [0, 0, 1],
        backgroundColor: ["#44f2c8", "#3fd2ff", "#2a3f67"],
        borderColor: "#101d36",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#bdd1f2" } },
      },
    },
  });
}

export function updateCharts(diagnostics = {}) {
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
}
