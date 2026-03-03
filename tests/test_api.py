from pathlib import Path

from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.dependency_graph import save_callers_index


client = TestClient(app)


def test_meta_lists_graph_endpoint() -> None:
    response = client.get("/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["graph"] == "/graph/{symbol}"


def test_graph_endpoint_returns_nodes_and_edges(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    graph_path = repo / ".legacylens" / "dependency_graph.json"
    save_callers_index(graph_path, {"READ-FILE": ["MAIN", "WORKER"]})

    response = client.get(f"/graph/READ-FILE?codebase_path={repo}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["symbol"] == "READ-FILE"
    assert any(node["id"] == "READ-FILE" and node["role"] == "target" for node in payload["nodes"])
    assert any(edge["target"] == "READ-FILE" for edge in payload["edges"])
