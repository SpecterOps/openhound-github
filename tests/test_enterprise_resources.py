from types import SimpleNamespace

from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise,
    enterprise_organizations,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict, pages: list[dict] | None = None):
        self.payload = payload
        self.pages = pages or []
        self.post_calls: list[tuple[str, dict]] = []
        self.paginate_calls: list[tuple[str, dict]] = []

    def post(self, path: str, json: dict):
        self.post_calls.append((path, json))
        return _FakeResponse(self.payload)

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter(self.pages)


def test_enterprise_resource_yields_single_record() -> None:
    client = _FakeClient(
        {
            "data": {
                "enterprise": {
                    "id": "E_1",
                    "slug": "acme",
                    "organizations": {
                        "nodes": [{"id": "O_1", "login": "org-1"}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                    },
                }
            }
        }
    )
    ctx = SourceContext(client=client, enterprise_name="acme")

    rows = list(enterprise(ctx))

    assert len(rows) == 1
    assert rows[0].id == "E_1"
    assert len(client.post_calls) == 1


def test_enterprise_organizations_paginates_all_pages() -> None:
    client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "enterprise": {
                        "organizations": {
                            "nodes": [{"id": "O_1", "login": "org-1"}],
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                        }
                    }
                }
            ],
            [
                {
                    "enterprise": {
                        "organizations": {
                            "nodes": [{"id": "O_2", "login": "org-2"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            ],
        ],
    )
    ctx = SourceContext(client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1")

    rows = list(enterprise_organizations.__wrapped__(enterprise_data, ctx))

    assert rows == [
        {"id": "O_1", "login": "org-1", "enterprise_node_id": "E_1", "enterprise_slug": "acme"},
        {"id": "O_2", "login": "org-2", "enterprise_node_id": "E_1", "enterprise_slug": "acme"},
    ]
    assert len(client.paginate_calls) == 1
