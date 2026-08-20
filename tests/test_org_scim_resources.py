import logging
from types import SimpleNamespace

import requests

from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    organization_resources,
    org_scim_organizations,
    scim_users,
)


class _HTTPErrorPaginateClient:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.paginate_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        response = requests.Response()
        response.status_code = self.status_code
        response.url = f"https://api.github.com{path}"
        raise requests.HTTPError(response=response)


class _FailingPaginateClient:
    def paginate(self, path: str, **kwargs):
        raise ConnectionError("SCIM endpoint unreachable")


def _ctx(client) -> SourceContext:
    return SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="acme")],
    )


def test_org_scim_organization_skips_unavailable_scope(caplog) -> None:
    client = _HTTPErrorPaginateClient(status_code=404)
    organization = SimpleNamespace(login="acme", node_id="O_1")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.organization"):
        rows = list(org_scim_organizations.__wrapped__(organization, _ctx(client)))

    assert rows == []
    assert any(
        "Skipping org_scim_organizations for organization 'acme': "
        "the GitHub scope does not expose SCIM endpoints"
        in message
        for message in caplog.messages
    )


def test_org_scim_users_skips_missing_permission(caplog) -> None:
    client = _HTTPErrorPaginateClient(status_code=403)
    scim_organization = SimpleNamespace(org_login="acme")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.organization"):
        rows = list(scim_users.__wrapped__(scim_organization, _ctx(client)))

    assert rows == []
    assert any(
        "Skipping scim_users for organization 'acme': "
        "the configured credentials do not have SCIM access"
        in message
        for message in caplog.messages
    )


def test_org_scim_users_logs_unexpected_failure_as_error(caplog) -> None:
    client = _FailingPaginateClient()
    scim_organization = SimpleNamespace(org_login="acme")

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        rows = list(scim_users.__wrapped__(scim_organization, _ctx(client)))

    assert rows == []
    assert any(
        "Error in resource 'scim_users' processing organization 'acme'"
        in message
        for message in caplog.messages
    )


def test_org_scim_users_are_bound_to_successful_scim_scope() -> None:
    client = _HTTPErrorPaginateClient(status_code=404)

    resources = {resource.name: resource for resource in organization_resources(_ctx(client))}

    assert resources["org_scim_organizations"]._pipe.parent.name == "organizations"
    assert resources["scim_users"]._pipe.parent.name == "org_scim_organizations"
