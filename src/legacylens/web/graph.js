let cy;

function toElements(graph) {
  const nodes = (graph.nodes || []).map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      role: node.role,
    },
  }));
  const edges = (graph.edges || []).map((edge, index) => ({
    data: {
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
    },
  }));
  return [...nodes, ...edges];
}

export function renderGraph(graph) {
  const container = document.getElementById("graph-view");
  if (!container || typeof window.cytoscape === "undefined") {
    return;
  }

  if (cy) {
    cy.destroy();
  }

  const elements = toElements(graph);
  cy = window.cytoscape({
    container,
    elements,
    style: [
      {
        selector: "node",
        style: {
          "background-color": "#3fd2ff",
          label: "data(label)",
          color: "#d6e6ff",
          "font-size": 10,
          "text-outline-color": "#0a1830",
          "text-outline-width": 2,
        },
      },
      {
        selector: "node[role = 'target']",
        style: {
          "background-color": "#44f2c8",
          width: 30,
          height: 30,
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
        },
      },
    ],
    layout: {
      name: "cose",
      animate: true,
      animationDuration: 250,
    },
  });
}
