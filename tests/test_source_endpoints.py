import importlib
import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from openhound_github.resources.enterprise import (
    SourceContext as EnterpriseResourceContext,
    enterprise,
)
from openhound_github.resources.organization import (
    OrgContext as OrganizationOrgContext,
    SourceContext as OrganizationResourceContext,
    secret_scanning_alerts,
    users,
)
from openhound_github.source import (
    DEFAULT_GITHUB_GRAPHQL_URL,
    DEFAULT_GITHUB_REST_API_URL,
    GithubEndpoints,
    GithubEnterpriseAppCredentials,
    GithubOrgAppCredentials,
    GithubTokenCredentials,
    resolve_github_endpoints,
)


def test_resolve_github_endpoints_uses_dotcom_defaults() -> None:
    assert resolve_github_endpoints() == GithubEndpoints(
        rest_api_url=DEFAULT_GITHUB_REST_API_URL,
        graphql_url=DEFAULT_GITHUB_GRAPHQL_URL,
    )


def test_resolve_github_endpoints_uses_explicit_endpoint_pair() -> None:
    assert resolve_github_endpoints(
        rest_api_url="https://ghe.example/api/v3/",
        graphql_url="https://ghe.example/api/graphql/",
    ) == GithubEndpoints(
        rest_api_url="https://ghe.example/api/v3",
        graphql_url="https://ghe.example/api/graphql",
    )


@pytest.mark.parametrize(
    ("rest_api_url", "graphql_url"),
    (
        ("https://ghe.example/api/v3", None),
        (None, "https://ghe.example/api/graphql"),
    ),
)
def test_resolve_github_endpoints_requires_explicit_pair(
    rest_api_url: str | None,
    graphql_url: str | None,
) -> None:
    with pytest.raises(
        ValueError,
        match="Both rest_api_url and graphql_url must be set",
    ):
        resolve_github_endpoints(
            rest_api_url=rest_api_url,
            graphql_url=graphql_url,
        )


def test_resolve_github_endpoints_preserves_legacy_host_behavior() -> None:
    assert resolve_github_endpoints(host="https://ghe.example/api/v3/") == GithubEndpoints(
        rest_api_url="https://ghe.example/api/v3",
        graphql_url="https://ghe.example/api/v3/graphql",
    )


@pytest.mark.parametrize(
    ("setting_name", "kwargs"),
    (
        ("host", {"host": "ghe.example/api/v3"}),
        (
            "rest_api_url",
            {
                "rest_api_url": "https://ghe.example/api/v3?token=secret",
                "graphql_url": "https://ghe.example/api/graphql",
            },
        ),
        (
            "graphql_url",
            {
                "rest_api_url": "https://ghe.example/api/v3",
                "graphql_url": "https://ghe.example/api/graphql#fragment",
            },
        ),
    ),
)
def test_resolve_github_endpoints_rejects_invalid_urls(
    setting_name: str,
    kwargs: dict[str, str],
) -> None:
    with pytest.raises(ValueError, match=setting_name):
        resolve_github_endpoints(**kwargs)


def test_org_source_context_carries_rest_and_graphql_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_module = importlib.import_module("openhound_github.source")
    captured_ctx = None

    class FakeRESTClient:
        def __init__(self, **kwargs) -> None:
            self.base_url = kwargs["base_url"]

    def capture_context(ctx):
        nonlocal captured_ctx
        captured_ctx = ctx
        return ()

    monkeypatch.setattr(source_module, "RESTClient", FakeRESTClient)
    monkeypatch.setattr(source_module, "organization_resources", capture_context)

    resources = source_module.source.__wrapped__(
        credentials=GithubTokenCredentials(token="token", org_name="acme"),
        emit_legacy_scim_correlations=False,
        rest_api_url="https://ghe.example/api/v3",
        graphql_url="https://ghe.example/api/graphql",
    )

    assert resources == ()
    assert captured_ctx is not None
    assert captured_ctx.organizations[0].client.base_url == "https://ghe.example/api/v3"
    assert (
        captured_ctx.organizations[0].graphql_client.base_url
        == "https://ghe.example/api/graphql"
    )


def test_enterprise_source_context_carries_rest_and_graphql_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_module = importlib.import_module("openhound_github.source")
    captured_ctx = None

    class FakeRESTClient:
        def __init__(self, **kwargs) -> None:
            self.base_url = kwargs["base_url"]

    def capture_context(ctx):
        nonlocal captured_ctx
        captured_ctx = ctx
        return ()

    monkeypatch.setattr(source_module, "RESTClient", FakeRESTClient)
    monkeypatch.setattr(source_module, "enterprise_resources", capture_context)

    resources = source_module.source.__wrapped__(
        credentials=GithubTokenCredentials(
            token="token",
            enterprise_name="acme-enterprise",
        ),
        emit_legacy_scim_correlations=False,
        rest_api_url="https://ghe.example/api/v3",
        graphql_url="https://ghe.example/api/graphql",
    )

    assert resources == ()
    assert captured_ctx is not None
    assert captured_ctx.client.base_url == "https://ghe.example/api/v3"
    assert captured_ctx.graphql_client.base_url == "https://ghe.example/api/graphql"
    assert captured_ctx.sso_client.base_url == "https://ghe.example/api/v3"
    assert captured_ctx.sso_graphql_client.base_url == "https://ghe.example/api/graphql"


def test_org_graphql_resource_uses_dedicated_graphql_client() -> None:
    rest_client = MagicMock()
    graphql_client = MagicMock()
    graphql_client.paginate.return_value = [
        [{"organization": {"membersWithRole": {"edges": []}}}]
    ]
    ctx = OrganizationResourceContext(
        client=rest_client,
        organizations=[
            OrganizationOrgContext(
                client=rest_client,
                graphql_client=graphql_client,
                org_name="acme",
            )
        ],
    )

    rows = list(inspect.unwrap(users._pipe.gen)(ctx))

    assert rows == []
    graphql_client.paginate.assert_called_once()
    assert graphql_client.paginate.call_args.args[0] == ""
    rest_client.paginate.assert_not_called()


def test_enterprise_graphql_resource_uses_dedicated_graphql_client() -> None:
    rest_client = MagicMock()
    graphql_client = MagicMock()
    graphql_client.post.return_value.json.return_value = {
        "data": {"enterprise": {"id": "E_1", "slug": "acme"}}
    }
    ctx = EnterpriseResourceContext(
        client=rest_client,
        graphql_client=graphql_client,
        enterprise_name="acme",
    )

    rows = list(inspect.unwrap(enterprise._pipe.gen)(ctx))

    assert len(rows) == 1
    graphql_client.post.assert_called_once()
    assert graphql_client.post.call_args.args[0] == ""
    rest_client.post.assert_not_called()


def test_secret_scanning_pat_validation_uses_configured_rest_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_module = importlib.import_module("openhound_github.resources.organization")
    rest_client = MagicMock()
    rest_client.base_url = "https://ghe.example/api/v3/"
    rest_client.paginate.return_value = [
        [
            {
                "state": "open",
                "secret_type": "github_personal_access_token",
                "secret": "ghp_example",
            }
        ]
    ]
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"node_id": "U_1"}
    get = MagicMock(return_value=response)
    monkeypatch.setattr(organization_module.requests, "get", get)
    ctx = OrganizationResourceContext(
        client=rest_client,
        organizations=[OrganizationOrgContext(client=rest_client, org_name="acme")],
    )

    rows = list(secret_scanning_alerts.__wrapped__(ctx))

    assert rows[0]["valid_token_user_node_id"] == "U_1"
    get.assert_called_once_with(
        "https://ghe.example/api/v3/user",
        headers={"Authorization": "Bearer ghp_example"},
        timeout=10,
    )


@pytest.mark.parametrize(
    ("credential_api_uri", "expected_auth_api_uri"),
    (
        (None, "https://ghe.example/api/v3"),
        ("https://ghe.example/custom/api/v3", "https://ghe.example/custom/api/v3"),
    ),
)
def test_org_app_source_uses_selected_auth_endpoint_and_both_api_clients(
    monkeypatch: pytest.MonkeyPatch,
    credential_api_uri: str | None,
    expected_auth_api_uri: str,
) -> None:
    source_module = importlib.import_module("openhound_github.source")
    captured_api_uris: list[str] = []
    captured_ctx = None

    class FakeGithubInstallation:
        def __init__(
            self,
            installation_id: str,
            jwt_issuer: str,
            private_key_path: str,
            api_uri: str,
        ) -> None:
            captured_api_uris.append(api_uri)

    class FakeRESTClient:
        def __init__(self, **kwargs) -> None:
            self.base_url = kwargs["base_url"]

    def fake_auth(*, installation, api_uri: str):
        captured_api_uris.append(api_uri)
        return object()

    def capture_context(ctx):
        nonlocal captured_ctx
        captured_ctx = ctx
        return ()

    monkeypatch.setattr(source_module, "GithubInstallation", FakeGithubInstallation)
    monkeypatch.setattr(source_module, "GitHubAppInstallationAuth", fake_auth)
    monkeypatch.setattr(source_module, "RESTClient", FakeRESTClient)
    monkeypatch.setattr(source_module, "organization_resources", capture_context)

    resources = source_module.source.__wrapped__(
        credentials=GithubOrgAppCredentials(
            client_id="Iv1.example",
            install_id="123",
            key_path="/tmp/github-app.pem",
            org_name="acme",
            api_uri=credential_api_uri,
        ),
        emit_legacy_scim_correlations=False,
        rest_api_url="https://ghe.example/api/v3",
        graphql_url="https://ghe.example/api/graphql",
    )

    assert resources == ()
    assert captured_api_uris == [
        expected_auth_api_uri,
        expected_auth_api_uri,
    ]
    assert captured_ctx.organizations[0].client.base_url == "https://ghe.example/api/v3"
    assert (
        captured_ctx.organizations[0].graphql_client.base_url
        == "https://ghe.example/api/graphql"
    )


@pytest.mark.parametrize(
    ("credential_api_uri", "expected_auth_api_uri"),
    (
        (None, "https://ghe.example/api/v3"),
        ("https://ghe.example/custom/api/v3", "https://ghe.example/custom/api/v3"),
    ),
)
def test_enterprise_app_source_uses_selected_auth_endpoint_and_both_api_clients(
    monkeypatch: pytest.MonkeyPatch,
    credential_api_uri: str | None,
    expected_auth_api_uri: str,
) -> None:
    source_module = importlib.import_module("openhound_github.source")
    captured_api_uris: list[str] = []
    captured_ctxs: list[object] = []

    class FakeGithubApp:
        def __init__(
            self, jwt_issuer: str, private_key_path: str, api_uri: str
        ) -> None:
            captured_api_uris.append(api_uri)
            self.installations = (
                SimpleNamespace(
                    id=11,
                    target_type="Organization",
                    account=SimpleNamespace(login="acme"),
                ),
                SimpleNamespace(
                    id=12,
                    target_type="Enterprise",
                    account=SimpleNamespace(slug="acme-enterprise"),
                ),
            )

    class FakeGithubInstallation:
        def __init__(
            self,
            installation_id: int,
            jwt_issuer: str,
            private_key_path: str,
            api_uri: str,
        ) -> None:
            captured_api_uris.append(api_uri)

    class FakeRESTClient:
        def __init__(self, **kwargs) -> None:
            self.base_url = kwargs["base_url"]

    def fake_auth(*, installation, api_uri: str):
        captured_api_uris.append(api_uri)
        return object()

    def capture_context(ctx):
        captured_ctxs.append(ctx)
        return ()

    monkeypatch.setattr(source_module, "GithubApp", FakeGithubApp)
    monkeypatch.setattr(source_module, "GithubInstallation", FakeGithubInstallation)
    monkeypatch.setattr(source_module, "GitHubAppInstallationAuth", fake_auth)
    monkeypatch.setattr(source_module, "RESTClient", FakeRESTClient)
    monkeypatch.setattr(source_module, "enterprise_resources", capture_context)
    monkeypatch.setattr(source_module, "organization_resources", capture_context)

    resources = source_module.source.__wrapped__(
        credentials=GithubEnterpriseAppCredentials(
            app_id="123456",
            key_path="/tmp/github-app.pem",
            enterprise_name="acme-enterprise",
            api_uri=credential_api_uri,
        ),
        emit_legacy_scim_correlations=False,
        rest_api_url="https://ghe.example/api/v3",
        graphql_url="https://ghe.example/api/graphql",
    )

    assert resources == ()
    assert captured_api_uris == [
        expected_auth_api_uri,
        expected_auth_api_uri,
        expected_auth_api_uri,
        expected_auth_api_uri,
        expected_auth_api_uri,
    ]
    assert len(captured_ctxs) == 2
    ctx = captured_ctxs[0]
    assert ctx.client.base_url == "https://ghe.example/api/v3"
    assert ctx.graphql_client.base_url == "https://ghe.example/api/graphql"
    assert ctx.organizations[0].client.base_url == "https://ghe.example/api/v3"
    assert ctx.organizations[0].graphql_client.base_url == "https://ghe.example/api/graphql"
