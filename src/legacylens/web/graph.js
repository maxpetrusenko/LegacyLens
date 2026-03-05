let cy;
let currentGraphData = null;

const EDGE_COLORS = {
  perform: "#44f2c8",
  call: "#3fd2ff",
  unknown: "#4f77b0",
};

function toElements(graph) {
  const targetId = graph.target || graph.nodes?.find((n) => n.role === "target")?.id;
  const nodes = (graph.nodes || []).map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      role: node.role,
      isTarget: node.role === "target" || node.id === targetId,
    },
  }));
  const edges = (graph.edges || []).map((edge, index) => ({
    data: {
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      relation: edge.relation || "unknown",
    },
  }));
  return [...nodes, ...edges];
}

function buildStyles() {
  return [
    {
      selector: "node",
      style: {
        "background-color": "#3fd2ff",
        label: "data(label)",
        color: "#173657",
        "font-size": 10,
        "text-outline-color": "#ffffff",
        "text-outline-width": 1.5,
        width: 24,
        height: 24,
      },
    },
    {
      selector: "node[isTarget = true]",
      style: {
        "background-color": "#44f2c8",
        width: 32,
        height: 32,
        "border-width": 3,
        "border-color": "#44f2c8",
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#4f77b0",
        "target-arrow-color": "#4f77b0",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        "arrow-scale": 0.8,
      },
    },
    {
      selector: "edge[relation = 'perform']",
      style: {
        "line-color": EDGE_COLORS.perform,
        "target-arrow-color": EDGE_COLORS.perform,
        width: 2.5,
      },
    },
    {
      selector: "edge[relation = 'call']",
      style: {
        "line-color": EDGE_COLORS.call,
        "target-arrow-color": EDGE_COLORS.call,
        "line-style": "dashed",
        "line-dash-pattern": [6, 4],
      },
    },
    {
      selector: "edge[relation = 'unknown']",
      style: {
        "line-color": EDGE_COLORS.unknown,
        "target-arrow-color": EDGE_COLORS.unknown,
        opacity: 0.6,
      },
    },
  ];
}

function getLayout(rootId) {
  return {
    name: "breadthfirst",
    root: rootId || undefined,
    directed: true,
    spacingFactor: 1.2,
    animate: true,
    animationDuration: 250,
    avoidOverlap: true,
    maximalAdjustments: 0,
  };
}

export function clearGraph() {
  if (cy) {
    cy.destroy();
    cy = null;
  }
  currentGraphData = null;
  const container = document.getElementById("graph-view");
  if (container) {
    container.innerHTML = "";
  }
}

export function renderGraph(graph) {
  const container = document.getElementById("graph-view");
  if (!container) {
    return;
  }

  if (!graph || (!Array.isArray(graph.nodes) && !Array.isArray(graph.edges))) {
    clearGraph();
    return;
  }

  if (typeof window.cytoscape === "undefined") {
    container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#6e84a5;font:400 0.85rem/1.4 var(--mono);">
        Graph visualization requires Cytoscape.js
      </div>
    `;
    return;
  }

  currentGraphData = graph;

  if (cy) {
    cy.destroy();
  }

  const elements = toElements(graph);
  const targetId = graph.target || graph.nodes?.find((n) => n.role === "target")?.id;

  cy = window.cytoscape({
    container,
    elements,
    style: buildStyles(),
    layout: getLayout(targetId),
  });

  cy.fit(undefined, 40);
}

export function getGraphStats() {
  if (!currentGraphData) {
    return { nodeCount: 0, edgeCount: 0, edgesByRelation: {} };
  }
  const edges = currentGraphData.edges || [];
  const edgesByRelation = { perform: 0, call: 0, unknown: 0 };
  for (const edge of edges) {
    const rel = edge.relation || "unknown";
    edgesByRelation[rel] = (edgesByRelation[rel] || 0) + 1;
  }
  return {
    nodeCount: (currentGraphData.nodes || []).length,
    edgeCount: edges.length,
    edgesByRelation,
  };
}
