from types import SimpleNamespace

from legacylens.config import Settings
from legacylens.vector_store import QdrantStore


class _CompatClient:
    def __init__(self) -> None:
        self.search_called = False

    def query_points(self, **_kwargs):
        raise RuntimeError('Unexpected Response: 404 (Not Found)')

    def search(self, **_kwargs):
        self.search_called = True
        return [SimpleNamespace(payload={"file_path": "x.cob", "line_start": 1, "line_end": 2, "text": "MOVE A TO B"}, score=0.42)]


class _ModernClient:
    def query_points(self, **_kwargs):
        return SimpleNamespace(points=[SimpleNamespace(payload={"file_path": "y.cob", "line_start": 5, "line_end": 6, "text": "STOP RUN"}, score=0.73)])


def test_search_uses_legacy_fallback_on_404() -> None:
    store = QdrantStore(Settings())
    client = _CompatClient()
    store.client = client

    hits = store.search([0.1, 0.2], limit=3)

    assert client.search_called is True
    assert len(hits) == 1
    assert hits[0].file_path == "x.cob"


def test_search_uses_query_points_when_available() -> None:
    store = QdrantStore(Settings())
    store.client = _ModernClient()

    hits = store.search([0.1, 0.2], limit=3)

    assert len(hits) == 1
    assert hits[0].file_path == "y.cob"
