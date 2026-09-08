import inspect
from types import SimpleNamespace

from openhound_github.resources.organization import OrgContext, SourceContext, workflows


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class _FakeClient:
    def __init__(
        self,
        workflow_pages: list[list[dict]],
        *,
        default_workflow_permissions: str = "read",
        can_approve_pull_request_reviews: bool = False,
        workflow_permission_responses: dict[str, dict] | None = None,
        workflow_permission_errors: set[str] | None = None,
    ):
        self.workflow_pages = workflow_pages
        self.default_workflow_permissions = default_workflow_permissions
        self.can_approve_pull_request_reviews = can_approve_pull_request_reviews
        self.workflow_permission_responses = workflow_permission_responses or {}
        self.workflow_permission_errors = workflow_permission_errors or set()
        self.get_calls: list[tuple[str, dict]] = []
        self.paginate_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter(self.workflow_pages)

    def get(self, path: str, **kwargs):
        self.get_calls.append((path, kwargs))
        if path.endswith("/actions/permissions/workflow"):
            if path in self.workflow_permission_errors:
                raise RuntimeError("workflow permissions unavailable")
            if path in self.workflow_permission_responses:
                return _FakeResponse(self.workflow_permission_responses[path])
            return _FakeResponse(
                {
                    "default_workflow_permissions": self.default_workflow_permissions,
                    "can_approve_pull_request_reviews": self.can_approve_pull_request_reviews,
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


def _repo_for_org(
    org_login: str, node_id: str, repository_name: str = "repo"
) -> SimpleNamespace:
    return SimpleNamespace(
        full_name=f"{org_login}/{repository_name}",
        name=repository_name,
        node_id=node_id,
        org_login=org_login,
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


def _workflow_transformer_generator():
    """Return the raw workflow transformer generator for dlt 1.26.0 tests.

    dlt does not expose a public accessor for the wrapped generator. The
    private pipe access stays isolated here so tests can preserve deferred()
    invocation behavior without spreading that dependency.
    """
    return inspect.unwrap(workflows._pipe.gen)


def _collect_workflows(repo, ctx) -> list[dict]:
    generator = _workflow_transformer_generator()
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


def test_workflows_cache_repository_permissions_by_organization_and_repository() -> None:
    acme_client = _FakeClient(
        [[_workflow_row(1)]],
        default_workflow_permissions="read",
        can_approve_pull_request_reviews=False,
    )
    other_client = _FakeClient(
        [[_workflow_row(2)]],
        default_workflow_permissions="write",
        can_approve_pull_request_reviews=True,
    )
    ctx = SourceContext(
        client=acme_client,
        organizations=[
            OrgContext(client=acme_client, org_name="acme"),
            OrgContext(client=other_client, org_name="other"),
        ],
    )

    acme_rows = _collect_workflows(_repo_for_org("acme", "REPO_1"), ctx)
    other_rows = _collect_workflows(_repo_for_org("other", "REPO_2"), ctx)

    assert acme_rows[0]["repository_default_workflow_permissions"] == "read"
    assert acme_rows[0]["repository_can_approve_pull_request_reviews"] is False
    assert other_rows[0]["repository_default_workflow_permissions"] == "write"
    assert other_rows[0]["repository_can_approve_pull_request_reviews"] is True
    assert ctx.repository_workflow_permissions_cache == {
        "acme/repo": {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        },
        "other/repo": {
            "default_workflow_permissions": "write",
            "can_approve_pull_request_reviews": True,
        },
    }


def test_workflows_cache_repository_permissions_by_repository_within_organization() -> None:
    client = _FakeClient(
        [[_workflow_row(1)]],
        workflow_permission_responses={
            "/repos/acme/repo/actions/permissions/workflow": {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
            "/repos/acme/other-repo/actions/permissions/workflow": {
                "default_workflow_permissions": "write",
                "can_approve_pull_request_reviews": True,
            },
        },
    )
    ctx = _ctx(client)

    repo_rows = _collect_workflows(_repo_for_org("acme", "REPO_1"), ctx)
    other_repo_rows = _collect_workflows(
        _repo_for_org("acme", "REPO_2", repository_name="other-repo"), ctx
    )

    assert repo_rows[0]["repository_default_workflow_permissions"] == "read"
    assert repo_rows[0]["repository_can_approve_pull_request_reviews"] is False
    assert other_repo_rows[0]["repository_default_workflow_permissions"] == "write"
    assert other_repo_rows[0]["repository_can_approve_pull_request_reviews"] is True
    assert [
        path for path, _kwargs in client.get_calls if path.endswith("/permissions/workflow")
    ] == [
        "/repos/acme/repo/actions/permissions/workflow",
        "/repos/acme/other-repo/actions/permissions/workflow",
    ]
    assert ctx.repository_workflow_permissions_cache == {
        "acme/repo": {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        },
        "acme/other-repo": {
            "default_workflow_permissions": "write",
            "can_approve_pull_request_reviews": True,
        },
    }


def test_workflows_continue_when_repository_permission_lookup_fails() -> None:
    permission_path = "/repos/acme/repo/actions/permissions/workflow"
    client = _FakeClient(
        [[_workflow_row(1)]],
        workflow_permission_errors={permission_path},
    )
    ctx = _ctx(client)

    rows = _collect_workflows(_repo(), ctx)
    _collect_workflows(_repo(), ctx)

    assert rows[0]["repository_default_workflow_permissions"] is None
    assert rows[0]["repository_can_approve_pull_request_reviews"] is None
    assert ctx.repository_workflow_permissions_cache == {"acme/repo": {}}
    assert [
        path for path, _kwargs in client.get_calls if path == permission_path
    ] == [permission_path]
