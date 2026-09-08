import logging
from types import SimpleNamespace

import requests

from openhound_github.models import EnterpriseScimOrganization, EnterpriseScimUser
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise,
    enterprise_admins,
    enterprise_external_identity,
    enterprise_organizations,
    enterprise_runner_group_memberships,
    enterprise_runner_group_organizations,
    enterprise_runner_groups,
    enterprise_runners,
    enterprise_resources,
    enterprise_scim_organizations,
    enterprise_scim_users,
    enterprise_saml_provider,
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


class _FailingPaginateClient(_FakeClient):
    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        raise ConnectionError("GraphQL endpoint unreachable")


class _PartiallyFailingPaginateClient(_FakeClient):
    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        yield from self.pages
        raise ConnectionError("GraphQL endpoint unreachable")


class _FailingPostClient(_FakeClient):
    def post(self, path: str, json: dict):
        self.post_calls.append((path, json))
        raise ConnectionError("GraphQL endpoint unreachable")


class _HTTPErrorPaginateClient(_FakeClient):
    def __init__(self, status_code: int):
        super().__init__(payload={})
        self.status_code = status_code

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        response = requests.Response()
        response.status_code = self.status_code
        response.url = f"https://api.github.com{path}"
        raise requests.HTTPError(response=response)


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
    ctx = SourceContext(
        client=client,
        enterprise_name="acme",
        deployment_type="ghes",
        ghes_version="3.22.1",
    )

    rows = list(enterprise(ctx))

    assert len(rows) == 1
    assert rows[0].id == "E_1"
    assert rows[0].github_deployment_type == "ghes"
    assert rows[0].ghes_version == "3.22.1"

    rows[0]._lookup = SimpleNamespace(enterprise_id=lambda: "E_1")
    assert rows[0].as_node.properties.github_deployment_type == "ghes"
    assert rows[0].as_node.properties.ghes_version == "3.22.1"
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


def test_enterprise_organizations_logs_and_returns_on_pagination_failure(caplog) -> None:
    client = _FailingPaginateClient(payload={})
    ctx = SourceContext(client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1")

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_organizations.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "Error in resource 'enterprise_organizations' processing enterprise 'acme'"
        in message
        for message in caplog.messages
    )


def test_enterprise_saml_provider_logs_and_returns_on_request_failure(caplog) -> None:
    client = _FailingPostClient(payload={})
    ctx = SourceContext(client=client, sso_client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1", name="Acme", slug="acme")

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_saml_provider.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "Error in resource 'enterprise_saml_provider' processing enterprise 'acme'"
        in message
        for message in caplog.messages
    )


def test_enterprise_saml_provider_logs_and_returns_when_enterprise_is_null(
    caplog,
) -> None:
    client = _FakeClient(payload={"data": {"enterprise": None}})
    ctx = SourceContext(client=client, sso_client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1", name="Acme", slug="acme")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_saml_provider.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "No enterprise object returned while fetching SAML provider for enterprise 'acme'"
        in record.getMessage()
        and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_enterprise_saml_provider_logs_and_returns_when_enterprise_is_missing(
    caplog,
) -> None:
    client = _FakeClient(payload={"data": {}})
    ctx = SourceContext(client=client, sso_client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1", name="Acme", slug="acme")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_saml_provider.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "No enterprise object returned while fetching SAML provider for enterprise 'acme'"
        in record.getMessage()
        and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_enterprise_saml_provider_logs_and_returns_when_provider_is_missing(
    caplog,
) -> None:
    client = _FakeClient(payload={"data": {"enterprise": {"ownerInfo": {}}}})
    ctx = SourceContext(client=client, sso_client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1", name="Acme", slug="acme")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_saml_provider.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "No enterprise SAML provider returned for enterprise 'acme'"
        in record.getMessage()
        and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_enterprise_admins_use_pat_backed_owner_info_graphql_client() -> None:
    assert enterprise_admins._hints["columns"]["role_id"]["data_type"] == "text"

    app_client = _FakeClient(payload={}, pages=[])
    app_graphql_client = _FakeClient(payload={}, pages=[])
    pat_client = _FakeClient(payload={}, pages=[])
    pat_graphql_client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "enterprise": {
                        "ownerInfo": {
                            "admins": {
                                "edges": [
                                    {"node": {"id": "U_1", "login": "alice"}},
                                    {"node": {"id": "U_2", "login": "bob"}},
                                ]
                            }
                        }
                    }
                }
            ]
        ],
    )
    ctx = SourceContext(
        client=app_client,
        graphql_client=app_graphql_client,
        sso_client=pat_client,
        sso_graphql_client=pat_graphql_client,
        enterprise_name="acme",
    )

    rows = list(enterprise_admins.__wrapped__(SimpleNamespace(id="E_1"), ctx))

    assert rows == [
        {
            "node_id": "U_1",
            "login": "alice",
            "assignment": "direct",
            "role_id": "owners",
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        },
        {
            "node_id": "U_2",
            "login": "bob",
            "assignment": "direct",
            "role_id": "owners",
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        },
    ]
    assert pat_graphql_client.paginate_calls[0][0] == ""
    assert "role: OWNER" in pat_graphql_client.paginate_calls[0][1]["json"]["query"]
    assert app_client.paginate_calls == []
    assert app_graphql_client.paginate_calls == []


def test_enterprise_admins_fall_back_to_org_enterprise_owners_without_pat() -> None:
    enterprise_client = _FakeClient(payload={}, pages=[])
    enterprise_graphql_client = _FakeClient(
        payload={},
        pages=[[{"enterprise": {"ownerInfo": None}}]],
    )
    org_client = _FakeClient(payload={}, pages=[])
    org_graphql_client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "organization": {
                        "enterpriseOwners": {
                            "nodes": [{"id": "U_1", "login": "alice"}]
                        }
                    }
                }
            ]
        ],
    )
    ctx = SourceContext(
        client=enterprise_client,
        graphql_client=enterprise_graphql_client,
        enterprise_name="acme",
        organizations=[
            SimpleNamespace(
                org_name="acme-org",
                client=org_client,
                graphql_client=org_graphql_client,
            )
        ],
    )

    rows = list(enterprise_admins.__wrapped__(SimpleNamespace(id="E_1"), ctx))

    assert rows == [
        {
            "node_id": "U_1",
            "login": "alice",
            "assignment": "direct",
            "role_id": "owners",
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        }
    ]
    assert enterprise_graphql_client.paginate_calls[0][0] == ""
    assert org_graphql_client.paginate_calls[0][0] == ""
    assert (
        org_graphql_client.paginate_calls[0][1]["json"]["variables"]["login"]
        == "acme-org"
    )


def test_enterprise_admins_fall_back_after_owner_info_request_failure(caplog) -> None:
    enterprise_graphql_client = _FailingPaginateClient(payload={})
    org_graphql_client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "organization": {
                        "enterpriseOwners": {
                            "nodes": [{"id": "U_1", "login": "alice"}]
                        }
                    }
                }
            ]
        ],
    )
    ctx = SourceContext(
        client=_FakeClient(payload={}),
        graphql_client=enterprise_graphql_client,
        enterprise_name="acme",
        organizations=[
            SimpleNamespace(
                org_name="acme-org",
                client=_FakeClient(payload={}),
                graphql_client=org_graphql_client,
            )
        ],
    )

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_admins.__wrapped__(SimpleNamespace(id="E_1"), ctx))

    assert rows[0]["node_id"] == "U_1"
    assert any(
        "trying organization.enterpriseOwners fallback" in message
        for message in caplog.messages
    )


def test_enterprise_admins_fall_back_after_partial_owner_info_pagination_failure(
    caplog,
) -> None:
    enterprise_graphql_client = _PartiallyFailingPaginateClient(
        payload={},
        pages=[
            [
                {
                    "enterprise": {
                        "ownerInfo": {
                            "admins": {
                                "edges": [{"node": {"id": "U_1", "login": "alice"}}]
                            }
                        }
                    }
                }
            ]
        ],
    )
    org_graphql_client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "organization": {
                        "enterpriseOwners": {
                            "nodes": [
                                {"id": "U_1", "login": "alice"},
                                {"id": "U_2", "login": "bob"},
                            ]
                        }
                    }
                }
            ]
        ],
    )
    ctx = SourceContext(
        client=_FakeClient(payload={}),
        graphql_client=enterprise_graphql_client,
        enterprise_name="acme",
        organizations=[
            SimpleNamespace(
                org_name="acme-org",
                client=_FakeClient(payload={}),
                graphql_client=org_graphql_client,
            )
        ],
    )

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_admins.__wrapped__(SimpleNamespace(id="E_1"), ctx))

    assert [row["node_id"] for row in rows] == ["U_1", "U_2"]
    assert len(org_graphql_client.paginate_calls) == 1
    assert any(
        "trying organization.enterpriseOwners fallback" in message
        for message in caplog.messages
    )


def test_enterprise_external_identity_logs_and_returns_on_pagination_failure(
    caplog,
) -> None:
    client = _FailingPaginateClient(payload={})
    ctx = SourceContext(client=client, sso_client=client, enterprise_name="acme")
    saml_provider = {
        "environment_slug": "acme",
        "github_deployment_id": "github.com",
    }

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_external_identity.__wrapped__(saml_provider, ctx))

    assert rows == []
    assert any(
        "Error in resource 'enterprise_external_identity' processing enterprise 'acme'"
        in message
        for message in caplog.messages
    )


def test_enterprise_scim_organization_skips_missing_permission(caplog) -> None:
    client = _HTTPErrorPaginateClient(status_code=403)
    ctx = SourceContext(client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_scim_organizations.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "Skipping enterprise_scim_organizations for enterprise 'acme': "
        "the configured credentials do not have SCIM access"
        in message
        for message in caplog.messages
    )


def test_enterprise_scim_organization_skips_unavailable_scope(caplog) -> None:
    client = _HTTPErrorPaginateClient(status_code=404)
    ctx = SourceContext(client=client, enterprise_name="acme")
    enterprise_data = SimpleNamespace(id="E_1")

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_scim_organizations.__wrapped__(enterprise_data, ctx))

    assert rows == []
    assert any(
        "Skipping enterprise_scim_organizations for enterprise 'acme': "
        "the GitHub scope does not expose SCIM endpoints"
        in message
        for message in caplog.messages
    )


def test_enterprise_scim_uses_enterprise_client_when_sso_client_is_present() -> None:
    enterprise_client = _FakeClient(payload={}, pages=[[]])
    sso_client = _FailingPaginateClient(payload={})
    ctx = SourceContext(
        client=enterprise_client,
        sso_client=sso_client,
        enterprise_name="acme",
    )
    enterprise_data = SimpleNamespace(id="E_1")

    rows = list(enterprise_scim_organizations.__wrapped__(enterprise_data, ctx))

    assert rows == [{"enterprise_node_id": "E_1", "enterprise_slug": "acme"}]
    assert enterprise_client.paginate_calls[0][0] == "/scim/v2/enterprises/acme/Users"
    assert sso_client.paginate_calls == []


def test_enterprise_scim_users_logs_unexpected_failure_as_error(caplog) -> None:
    client = _FailingPaginateClient(payload={})
    ctx = SourceContext(client=client, enterprise_name="acme")
    scim_organization = SimpleNamespace(enterprise_node_id="E_1")

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_scim_users.__wrapped__(scim_organization, ctx))

    assert rows == []
    assert any(
        "Error in resource 'enterprise_scim_users' processing enterprise 'acme'"
        in message
        for message in caplog.messages
    )


def test_enterprise_resources_register_scim_by_default() -> None:
    ctx = SourceContext(client=_FakeClient(payload={}), enterprise_name="acme")

    resources = {resource.name: resource for resource in enterprise_resources(ctx)}

    assert "enterprise_scim_organizations" in resources
    assert "enterprise_scim_users" in resources
    assert "enterprise_scim_groups" in resources
    assert (
        resources["enterprise_scim_organizations"].validator.model
        is EnterpriseScimOrganization
    )
    assert resources["enterprise_scim_users"].validator.model is EnterpriseScimUser


def test_enterprise_scim_children_are_bound_to_successful_scim_scope() -> None:
    ctx = SourceContext(client=_FakeClient(payload={}), enterprise_name="acme")

    resources = {resource.name: resource for resource in enterprise_resources(ctx)}

    assert resources["enterprise_scim_organizations"]._pipe.parent.name == "enterprise"
    assert (
        resources["enterprise_scim_users"]._pipe.parent.name
        == "enterprise_scim_organizations"
    )
    assert (
        resources["enterprise_scim_groups"]._pipe.parent.name
        == "enterprise_scim_organizations"
    )


def test_enterprise_runner_groups_use_pat_backed_client() -> None:
    app_client = _FakeClient(payload={})
    pat_client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "id": 2,
                    "name": "enterprise-runners",
                    "visibility": "selected",
                }
            ]
        ],
    )
    ctx = SourceContext(
        client=app_client,
        sso_client=pat_client,
        enterprise_name="acme",
    )
    enterprise_data = SimpleNamespace(id="E_1")

    rows = list(enterprise_runner_groups.__wrapped__(enterprise_data, ctx))

    assert rows == [
        {
            "id": 2,
            "name": "enterprise-runners",
            "visibility": "selected",
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        }
    ]
    assert pat_client.paginate_calls[0][0] == "/enterprises/acme/actions/runner-groups"
    assert app_client.paginate_calls == []


def test_enterprise_runners_and_memberships_use_enterprise_scope() -> None:
    pat_client = _FakeClient(
        payload={},
        pages=[[{"id": 9, "name": "runner-1"}]],
    )
    ctx = SourceContext(
        client=_FakeClient(payload={}),
        sso_client=pat_client,
        enterprise_name="acme",
    )
    enterprise_data = SimpleNamespace(id="E_1")

    runner_rows = list(enterprise_runners.__wrapped__(enterprise_data, ctx))

    assert runner_rows == [
        {
            "id": 9,
            "name": "runner-1",
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        }
    ]

    group = SimpleNamespace(
        id=2,
        visibility="selected",
        enterprise_node_id="E_1",
        enterprise_slug="acme",
    )
    membership_rows = list(
        enterprise_runner_group_memberships.__wrapped__(group, ctx)
    )

    assert membership_rows == [
        {
            "runner_group_id": 2,
            "runner_id": 9,
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        }
    ]
    assert pat_client.paginate_calls == [
        (
            "/enterprises/acme/actions/runners",
            {"params": {"per_page": 100}, "data_selector": "runners"},
        ),
        (
            "/enterprises/acme/actions/runner-groups/2/runners",
            {"params": {"per_page": 100}, "data_selector": "runners"},
        ),
    ]


def test_enterprise_runner_group_organizations_emit_group_assignments() -> None:
    pat_client = _FakeClient(
        payload={},
        pages=[
            [
                {
                    "node_id": "ORG_1",
                    "login": "acme-org",
                }
            ]
        ],
    )
    ctx = SourceContext(
        client=_FakeClient(payload={}),
        sso_client=pat_client,
        enterprise_name="acme",
    )
    group = SimpleNamespace(
        id=2,
        visibility="selected",
        enterprise_node_id="E_1",
        enterprise_slug="acme",
    )

    rows = list(enterprise_runner_group_organizations.__wrapped__(group, ctx))

    assert rows == [
        {
            "node_id": "ORG_1",
            "login": "acme-org",
            "runner_group_id": 2,
            "enterprise_node_id": "E_1",
            "enterprise_slug": "acme",
        }
    ]
    assert pat_client.paginate_calls == [
        (
            "/enterprises/acme/actions/runner-groups/2/organizations",
            {"params": {"per_page": 100}, "data_selector": "organizations"},
        )
    ]


def test_enterprise_runner_group_organizations_skip_non_selected_groups() -> None:
    pat_client = _FakeClient(payload={}, pages=[[{"node_id": "ORG_1"}]])
    ctx = SourceContext(
        client=_FakeClient(payload={}),
        sso_client=pat_client,
        enterprise_name="acme",
    )
    group = SimpleNamespace(
        id=1,
        visibility="all",
        enterprise_node_id="E_1",
        enterprise_slug="acme",
    )

    rows = list(enterprise_runner_group_organizations.__wrapped__(group, ctx))

    assert rows == []
    assert pat_client.paginate_calls == []
