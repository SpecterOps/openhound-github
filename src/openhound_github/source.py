import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Union
from urllib.parse import urlparse

import dlt
from dlt.common.configuration import configspec
from dlt.common.configuration.specs import CredentialsConfiguration
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import (
    HeaderLinkPaginator,
)

from openhound_github.auth import (
    GithubApp,
    GitHubAppInstallationAuth,
    GithubInstallation,
    resolve_github_app_jwt_issuer,
)
from openhound_github.helpers import (
    DEFAULT_GITHUB_GRAPHQL_URL,
    DEFAULT_GITHUB_REST_API_URL,
    github_retry_policy,
)
from openhound_github.main import app
from openhound_github.models.saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    github_deployment_context,
)

from .resources.enterprise import enterprise_resources
from .resources.organization import organization_resources

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class GithubEndpoints:
    rest_api_url: str
    graphql_url: str


def _normalize_endpoint_url(url: str, setting_name: str) -> str:
    normalized_url = url.strip().rstrip("/")
    parsed = urlparse(normalized_url)
    if (
        not normalized_url
        or parsed.scheme != "https"
        or not parsed.hostname
    ):
        raise ValueError(f"{setting_name} must be an absolute HTTPS URL")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{setting_name} must not contain user-info, query strings, or fragments"
        )
    return normalized_url


def _endpoint_origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    port = parsed.port
    if (parsed.scheme.lower(), port) in {("http", 80), ("https", 443)}:
        port = None
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def _resolve_app_auth_api_uri(
    credentials_api_uri: str | None,
    rest_api_url: str,
) -> str:
    if credentials_api_uri is None:
        return rest_api_url

    auth_api_uri = _normalize_endpoint_url(credentials_api_uri, "credentials.api_uri")
    if _endpoint_origin(auth_api_uri) != _endpoint_origin(rest_api_url):
        raise ValueError(
            "credentials.api_uri origin must match rest_api_url origin for GitHub App authentication"
        )
    return auth_api_uri


def _legacy_graphql_url(rest_api_url: str) -> str:
    if rest_api_url.endswith("/api/v3"):
        return f"{rest_api_url.removesuffix('/v3')}/graphql"
    return f"{rest_api_url}/graphql"


def resolve_github_endpoints(
    *,
    host: str = DEFAULT_GITHUB_REST_API_URL,
    rest_api_url: str | None = None,
    graphql_url: str | None = None,
) -> GithubEndpoints:
    """Resolve GitHub REST and GraphQL endpoints from new and legacy settings."""
    if (rest_api_url is None) != (graphql_url is None):
        raise ValueError(
            "Both rest_api_url and graphql_url must be set when overriding GitHub endpoints"
        )

    if rest_api_url is not None and graphql_url is not None:
        resolved_endpoints = GithubEndpoints(
            rest_api_url=_normalize_endpoint_url(rest_api_url, "rest_api_url"),
            graphql_url=_normalize_endpoint_url(graphql_url, "graphql_url"),
        )
        if _endpoint_origin(resolved_endpoints.rest_api_url) != _endpoint_origin(
            resolved_endpoints.graphql_url
        ):
            raise ValueError(
                "rest_api_url origin must match graphql_url origin"
            )
        return resolved_endpoints

    legacy_rest_api_url = _normalize_endpoint_url(host, "host")
    if legacy_rest_api_url == DEFAULT_GITHUB_REST_API_URL:
        return GithubEndpoints(
            rest_api_url=DEFAULT_GITHUB_REST_API_URL,
            graphql_url=DEFAULT_GITHUB_GRAPHQL_URL,
        )

    return GithubEndpoints(
        rest_api_url=legacy_rest_api_url,
        graphql_url=_legacy_graphql_url(legacy_rest_api_url),
    )


@dataclass
class OrgContext:
    client: RESTClient
    org_name: str
    graphql_client: RESTClient | None = None
    enterprise_name: str | None = None
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN


@dataclass
class SourceContext:
    organizations: list[OrgContext] | None = field(default_factory=list)
    client: RESTClient | None = None
    graphql_client: RESTClient | None = None
    sso_client: RESTClient | None = None
    sso_graphql_client: RESTClient | None = None
    enterprise_name: str | None = None
    emit_legacy_scim_correlations: bool = False
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN
    cache_lock: Lock = field(default_factory=Lock)
    organizations_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    app_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    team_rest_cache: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    actions_permissions_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    runner_permissions_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    workflow_permissions_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def org_names(self) -> list[str]:
        return [org.org_name for org in self.organizations or []]


def _canonicalize_org_names(ctx: SourceContext) -> None:
    for org in ctx.organizations or []:
        configured_name = org.org_name
        try:
            org_data = org.client.get(f"/orgs/{configured_name}").json()
        except Exception as exc:
            logger.warning(
                "Unable to resolve canonical GitHub login for organization '%s': %s",
                configured_name,
                exc,
            )
            continue

        canonical_name = org_data.get("login")
        if not isinstance(canonical_name, str) or not canonical_name:
            logger.warning(
                "GitHub organization response for '%s' did not include a canonical login",
                configured_name,
            )
            continue

        org.org_name = canonical_name
        ctx.organizations_cache[canonical_name] = org_data


@configspec
class GithubCredentials(CredentialsConfiguration):
    org_name: str | None = None
    enterprise_name: str | None = None

    def auth(self):
        pass


@configspec
class GithubEnterpriseAppCredentials(CredentialsConfiguration):
    client_id: str | None = None
    app_id: str | None = None
    key_path: str = None
    enterprise_name: str = None
    pat_token: str | None = None
    api_uri: str | None = None

    @property
    def auth(self) -> str:
        return "enterprise_app"


@configspec
class GithubOrgAppCredentials(CredentialsConfiguration):
    client_id: str = None
    install_id: str = None
    key_path: str = None
    org_name: str = None
    api_uri: str | None = None

    @property
    def auth(self) -> str:
        return "org_app"


@configspec
class GithubTokenCredentials(GithubCredentials):
    token: str = None

    @property
    def auth(self) -> str:
        return "token"

    @property
    def header(self) -> str:
        return f"{self.token}"


@app.source(name="github", max_table_nesting=0)
def source(
    credentials: Union[
        GithubEnterpriseAppCredentials, GithubOrgAppCredentials, GithubTokenCredentials
    ] = dlt.secrets.value,
    host: str = DEFAULT_GITHUB_REST_API_URL,
    emit_legacy_scim_correlations: bool | None = dlt.config.value,
    rest_api_url: str | None = None,
    graphql_url: str | None = None,
):
    """DLT source, defines GitHub collection resources and transformers.

    Args:
        credentials (Union[GithubEnterpriseAppCredentials, GithubOrgAppCredentials, GithubTokenCredentials]): The GitHub credentials.
        host (str): Legacy base GitHub REST API URL used for API calls.
        emit_legacy_scim_correlations (bool | None): Whether to emit legacy SCIM correlation relationships.
        rest_api_url (str): The GitHub REST API base URL.
        graphql_url (str): The GitHub GraphQL endpoint URL.
    """
    endpoints = resolve_github_endpoints(
        host=host,
        rest_api_url=rest_api_url,
        graphql_url=graphql_url,
    )
    github_deployment_id, github_web_origin = github_deployment_context(
        endpoints.rest_api_url
    )

    def api_client(base_url: str, auth: AuthConfigBase) -> RESTClient:
        return RESTClient(
            base_url=base_url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            auth=auth,
            paginator=HeaderLinkPaginator(),
            session=requests.Client(
                status_codes=tuple(range(500, 600)),
                retry_condition=github_retry_policy(auth),
            ).session,
        )

    def clients(auth: AuthConfigBase) -> tuple[RESTClient, RESTClient]:
        return (
            api_client(endpoints.rest_api_url, auth),
            api_client(endpoints.graphql_url, auth),
        )

    def token_clients(token: str) -> tuple[RESTClient, RESTClient]:
        return clients(BearerTokenAuth(token=token))

    if credentials.auth == "enterprise_app":
        auth_api_uri = _resolve_app_auth_api_uri(
            credentials.api_uri,
            endpoints.rest_api_url,
        )
        jwt_issuer = resolve_github_app_jwt_issuer(
            client_id=credentials.client_id,
            app_id=credentials.app_id,
        )
        ctx = SourceContext(
            enterprise_name=credentials.enterprise_name,
            emit_legacy_scim_correlations=bool(emit_legacy_scim_correlations),
            github_deployment_id=github_deployment_id,
            github_web_origin=github_web_origin,
        )
        if credentials.pat_token:
            ctx.sso_client, ctx.sso_graphql_client = token_clients(
                credentials.pat_token
            )
        github_app_session = GithubApp(
            jwt_issuer=jwt_issuer,
            private_key_path=credentials.key_path,
            api_uri=auth_api_uri,
        )
        for installation in github_app_session.installations:
            if installation.target_type == "Organization":
                org_installation = GithubInstallation(
                    installation_id=installation.id,
                    jwt_issuer=jwt_issuer,
                    private_key_path=credentials.key_path,
                    api_uri=auth_api_uri,
                )
                org_client, org_graphql_client = clients(
                    GitHubAppInstallationAuth(
                        installation=org_installation,
                        api_uri=auth_api_uri,
                    )
                )
                ctx.organizations.append(
                    OrgContext(
                        org_name=installation.account.login,
                        client=org_client,
                        graphql_client=org_graphql_client,
                        enterprise_name=credentials.enterprise_name,
                        github_deployment_id=github_deployment_id,
                        github_web_origin=github_web_origin,
                    )
                )
            if installation.target_type == "Enterprise":
                es_installation = GithubInstallation(
                    installation_id=installation.id,
                    jwt_issuer=jwt_issuer,
                    private_key_path=credentials.key_path,
                    api_uri=auth_api_uri,
                )
                ctx.client, ctx.graphql_client = clients(
                    GitHubAppInstallationAuth(
                        installation=es_installation,
                        api_uri=auth_api_uri,
                    )
                )

        return (*enterprise_resources(ctx), *organization_resources(ctx))

    elif credentials.auth == "org_app":
        auth_api_uri = _resolve_app_auth_api_uri(
            credentials.api_uri,
            endpoints.rest_api_url,
        )
        ctx = SourceContext(
            enterprise_name=None,
            github_deployment_id=github_deployment_id,
            github_web_origin=github_web_origin,
        )
        org_installation = GithubInstallation(
            installation_id=credentials.install_id,
            jwt_issuer=credentials.client_id,
            private_key_path=credentials.key_path,
            api_uri=auth_api_uri,
        )
        org_client, org_graphql_client = clients(
            GitHubAppInstallationAuth(
                installation=org_installation,
                api_uri=auth_api_uri,
            )
        )
        ctx.organizations.append(
            OrgContext(
                org_name=credentials.org_name,
                client=org_client,
                graphql_client=org_graphql_client,
                github_deployment_id=github_deployment_id,
                github_web_origin=github_web_origin,
            )
        )

        _canonicalize_org_names(ctx)
        return organization_resources(ctx)

    else:
        if credentials.enterprise_name:
            token_api_client, token_graphql_client = token_clients(credentials.token)
            ctx = SourceContext(
                client=token_api_client,
                graphql_client=token_graphql_client,
                sso_client=token_api_client,
                sso_graphql_client=token_graphql_client,
                enterprise_name=credentials.enterprise_name,
                emit_legacy_scim_correlations=bool(emit_legacy_scim_correlations),
                github_deployment_id=github_deployment_id,
                github_web_origin=github_web_origin,
            )
            return enterprise_resources(ctx)

        token_api_client, token_graphql_client = token_clients(credentials.token)
        ctx = SourceContext(
            github_deployment_id=github_deployment_id,
            github_web_origin=github_web_origin,
        )
        ctx.organizations.append(
            OrgContext(
                org_name=credentials.org_name,
                client=token_api_client,
                graphql_client=token_graphql_client,
                github_deployment_id=github_deployment_id,
                github_web_origin=github_web_origin,
            )
        )
        _canonicalize_org_names(ctx)
        return organization_resources(ctx)
