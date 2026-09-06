import inspect
from types import SimpleNamespace

from openhound_github.resources.organization import OrgContext, SourceContext, workflows


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class _FakeClient:
    def __init__(self, workflow_pages: list[list[dict]]):
        self.workflow_pages = workflow_pages
        self.get_calls: list[tuple[str, dict]] = []
        self.paginate_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter(self.workflow_pages)

    def get(self, path: str, **kwargs):
        self.get_calls.append((path, kwargs))
        if path.endswith("/actions/permissions/workflow"):
            return _FakeResponse(
                {
                    "default_workflow_permissions": "read",
                    "can_approve_pull_request_reviews": False,
                }
            )
        return _FakeResponse({"content": "am9iczoge30="})


def _repo() -> SimpleNamespace:
    return SimpleNamespace(
        full_name="acme/repo",
        name="repo",
        node_id="REPO_1",
        org_login="acme",
        default_branch="main",
    )


def _ctx(client: _FakeClient) -> SourceContext:
    return SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="acme")],
    )


def _workflow_row(workflow_id: int, state: str = "active") -> dict:
    return {
        "id": workflow_id,
        "node_id": f"W_{workflow_id}",
        "name": f"workflow-{workflow_id}",
        "path": f".github/workflows/{workflow_id}.yml",
        "state": state,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "url": f"https://api.github.test/repos/acme/repo/actions/workflows/{workflow_id}",
    }


def _collect_workflows(repo, ctx) -> list[dict]:
    generator = inspect.unwrap(workflows._pipe.gen)
    return [deferred() for deferred in generator(repo, ctx)]


def test_workflows_skip_repository_permission_lookup_without_active_workflows() -> None:
    client = _FakeClient([[_workflow_row(1, state="disabled_manually")]])

    rows = _collect_workflows(_repo(), _ctx(client))

    assert rows == []
    assert client.get_calls == []


def test_workflows_cache_repository_permissions_for_active_workflows() -> None:
    client = _FakeClient([[_workflow_row(1), _workflow_row(2)]])
    ctx = _ctx(client)

    rows = _collect_workflows(_repo(), ctx)
    _collect_workflows(_repo(), ctx)

    assert [row["repository_default_workflow_permissions"] for row in rows] == [
        "read",
        "read",
    ]
    assert [row["repository_can_approve_pull_request_reviews"] for row in rows] == [
        False,
        False,
    ]
    assert [
        path for path, _kwargs in client.get_calls if path.endswith("/permissions/workflow")
    ] == ["/repos/acme/repo/actions/permissions/workflow"]
