from types import SimpleNamespace

from dlt.sources.helpers import requests

from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    org_runner_group_access,
    org_runner_group_memberships,
)


class _FakeClient:
    def __init__(self, pages: dict[str, list[list[dict]]]):
        self.pages = pages
        self.paginate_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter(self.pages.get(path, []))


class _FailingClient(_FakeClient):
    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        raise requests.RequestException("runner group membership unavailable")


def _ctx(client: _FakeClient) -> SourceContext:
    return SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="acme")],
    )


def test_org_runner_group_access_collects_selected_repository_policy() -> None:
    client = _FakeClient(
        {
            "/orgs/acme/actions/runner-groups/1/repositories": [
                [{"node_id": "REPO_1"}, {"node_id": "REPO_2"}]
            ]
        }
    )
    group = SimpleNamespace(
        id=1,
        name="Default",
        visibility="selected",
        allows_public_repositories=False,
        restricted_to_workflows=True,
        inherited=True,
        org_login="acme",
    )

    rows = list(org_runner_group_access.__wrapped__(group, _ctx(client)))

    assert rows == [
        {
            "runner_group_id": 1,
            "runner_group_name": "Default",
            "runner_group_visibility": "selected",
            "allows_public_repositories": False,
            "restricted_to_workflows": True,
            "inherited": True,
            "accessible_repo_node_ids": ["REPO_1", "REPO_2"],
            "org_login": "acme",
        }
    ]
    assert client.paginate_calls == [
        (
            "/orgs/acme/actions/runner-groups/1/repositories",
            {"params": {"per_page": 100}, "data_selector": "repositories"},
        )
    ]


def test_inherited_org_runner_group_access_skips_runner_membership_query() -> None:
    client = _FakeClient({})
    access = {
        "runner_group_id": 1,
        "runner_group_name": "Default",
        "runner_group_visibility": "all",
        "allows_public_repositories": False,
        "inherited": True,
        "accessible_repo_node_ids": [],
        "org_login": "acme",
    }

    rows = list(org_runner_group_memberships.__wrapped__(access, _ctx(client)))

    assert rows == []
    assert client.paginate_calls == []


def test_native_org_runner_group_access_collects_runner_memberships() -> None:
    client = _FakeClient(
        {"/orgs/acme/actions/runner-groups/1/runners": [[{"id": 9}]]}
    )
    access = {
        "runner_group_id": 1,
        "runner_group_name": "Default",
        "runner_group_visibility": "all",
        "allows_public_repositories": False,
        "inherited": False,
        "accessible_repo_node_ids": [],
        "org_login": "acme",
    }

    rows = list(org_runner_group_memberships.__wrapped__(access, _ctx(client)))

    assert rows == [
        {
            "runner_group_id": 1,
            "runner_group_name": "Default",
            "runner_id": 9,
            "runner_group_visibility": "all",
            "allows_public_repositories": False,
            "accessible_repo_node_ids": [],
            "org_login": "acme",
        }
    ]
    assert client.paginate_calls == [
        (
            "/orgs/acme/actions/runner-groups/1/runners",
            {"params": {"per_page": 100}, "data_selector": "runners"},
        )
    ]


def test_native_org_runner_group_membership_request_failure_yields_no_rows() -> None:
    client = _FailingClient({})
    access = {
        "runner_group_id": 1,
        "runner_group_name": "Default",
        "runner_group_visibility": "all",
        "allows_public_repositories": False,
        "inherited": False,
        "accessible_repo_node_ids": [],
        "org_login": "acme",
    }

    rows = list(org_runner_group_memberships.__wrapped__(access, _ctx(client)))

    assert rows == []
    assert client.paginate_calls == [
        (
            "/orgs/acme/actions/runner-groups/1/runners",
            {"params": {"per_page": 100}, "data_selector": "runners"},
        )
    ]
