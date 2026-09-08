from types import SimpleNamespace

from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    repository_deploy_keys,
)


class _FakeClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.paginate_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        if self.error:
            raise self.error
        return iter([])


def _ctx(client: _FakeClient) -> SourceContext:
    return SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="acme")],
    )


def _repository(deploy_key_count: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="REPO_1",
        name="repo",
        org_login="acme",
        deploy_key_count=deploy_key_count,
    )


def test_repository_deploy_keys_queries_repository_keys_endpoint() -> None:
    client = _FakeClient()

    rows = list(repository_deploy_keys.__wrapped__(_repository(1), _ctx(client)))

    assert rows == []
    assert client.paginate_calls == [
        ("/repos/acme/repo/keys", {"params": {"per_page": 100}})
    ]


def test_repository_deploy_keys_skips_repository_when_request_fails() -> None:
    client = _FakeClient(error=PermissionError("403 Forbidden"))

    rows = list(repository_deploy_keys.__wrapped__(_repository(None), _ctx(client)))

    assert rows == []
    assert client.paginate_calls == [
        ("/repos/acme/repo/keys", {"params": {"per_page": 100}})
    ]


def test_repository_deploy_keys_skips_query_when_repository_has_no_keys() -> None:
    client = _FakeClient()

    rows = list(repository_deploy_keys.__wrapped__(_repository(0), _ctx(client)))

    assert rows == []
    assert client.paginate_calls == []
