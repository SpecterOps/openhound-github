from typing import Any, Optional, Union

import dlt
from dlt.common.configuration import configspec
from dlt.common.configuration.specs import CredentialsConfiguration
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator

from openhound_github.auth import create_github_jwt_session
from openhound_github.main import app
from openhound_github.resources.enterprise import (
    _enterprise_member_records,
    _enterprise_profile_and_orgs,
    _enterprise_saml_records,
    enterprise,
    enterprise_admin_roles,
    enterprise_admins,
    enterprise_external_identities,
    enterprise_managed_users,
    enterprise_organizations,
    enterprise_role_teams,
    enterprise_role_users,
    enterprise_roles,
    enterprise_saml_provider,
    enterprise_team_members,
    enterprise_team_organizations,
    enterprise_team_roles,
    enterprise_teams,
    enterprise_users,
)
from openhound_github.resources.organization import (
    app_installations,
    applications,
    branch_protection_rules,
    branches,
    environment_branch_policies,
    environment_secrets,
    environment_variables,
    environments,
    external_identities,
    org_role_members,
    org_role_teams,
    org_roles,
    org_runner_group_memberships,
    org_runners,
    organization_secrets,
    organization_variables,
    organizations,
    pat_repo_access,
    personal_access_token_requests,
    personal_access_tokens,
    repo_role_assignments,
    repo_runners,
    repository_roles,
    repository_secrets,
    repository_variables,
    repositories,
    repositories_graphql,
    runner_groups,
    saml_provider,
    scim_users,
    secret_scanning_alerts,
    selected_organization_secrets,
    selected_organization_variables,
    team_members,
    team_roles,
    teams,
    users,
    workflows,
)
from openhound_github.source_context import OrgContext, SourceContext


@configspec
class GithubCredentials(CredentialsConfiguration):
    org_name: str | None = None
    enterprise_name: str | None = None

    def auth(self):
        pass


@configspec
class GithubAppCredentials(GithubCredentials):
    client_id: str | None = None
    app_id: str | None = None
    key_path: str | None = None
    api_uri: str = "https://api.github.com"

    def auth(self) -> str:
        return "app"

    @property
    def header(self) -> str:
        github_access_token = create_github_jwt_session(
            org_name=self.org_name,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=self.app_id,
            api_uri=self.api_uri,
        ).get_access_token()
        return github_access_token

    def header_for_installation(self, installation_id: int | str) -> str:
        return create_github_jwt_session(
            org_name=None,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=str(installation_id),
            api_uri=self.api_uri,
        ).get_access_token()

    def installations(self) -> list[dict[str, Any]]:
        return create_github_jwt_session(
            org_name=None,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=self.app_id,
            api_uri=self.api_uri,
        ).list_installations()


@configspec
class GithubTokenCredentials(GithubCredentials):
    token: str | None = None

    def auth(self) -> str:
        return "token"

    @property
    def header(self) -> str:
        return f"{self.token}"


def _org_collection_resources(ctx: SourceContext) -> tuple:
    repos_resource = repositories(ctx)
    environments_resource = repos_resource | environments(ctx)
    personal_access_tokens_resource = personal_access_tokens(ctx)
    org_resource = organizations(ctx)
    org_role_resource = org_roles(ctx)
    teams_resource = teams(ctx)
    repositories_graphql_resource = repositories_graphql(ctx)
    app_installs_resource = app_installations(ctx)
    runner_groups_resource = runner_groups(ctx)
    branch_prot_rules_resource = (
        repositories_graphql_resource | branch_protection_rules(ctx)
    )
    organization_secrets_resource = organization_secrets(ctx)
    organization_vars_resource = organization_variables(ctx)

    return (
        org_resource,
        users(ctx),
        org_role_resource,
        org_role_resource | org_role_members(ctx),
        org_role_resource | org_role_teams(ctx),
        repos_resource,
        repos_resource | repository_roles(ctx),
        repos_resource | workflows(ctx),
        repos_resource | repo_runners(ctx),
        repos_resource | repository_secrets(ctx),
        repos_resource | repository_variables(ctx),
        repos_resource | repo_role_assignments(ctx),
        environments_resource,
        environments_resource | environment_variables(ctx),
        environments_resource | environment_secrets(ctx),
        environments_resource | environment_branch_policies(ctx),
        teams_resource,
        teams_resource | team_members(ctx),
        teams_resource | team_roles(),
        runner_groups_resource,
        org_runners(ctx),
        org_runner_group_memberships(ctx),
        personal_access_tokens_resource,
        personal_access_tokens_resource | pat_repo_access(ctx),
        organization_secrets_resource,
        organization_secrets_resource | selected_organization_secrets(ctx),
        organization_vars_resource,
        organization_vars_resource | selected_organization_variables(ctx),
        personal_access_token_requests(ctx),
        scim_users(ctx),
        repositories_graphql_resource,
        repositories_graphql_resource | branches(ctx),
        branch_prot_rules_resource,
        secret_scanning_alerts(ctx),
        saml_provider(ctx),
        external_identities(ctx),
        app_installs_resource,
        app_installs_resource | applications(ctx),
    )


def _enterprise_collection_resources(
    ctx: SourceContext,
    enterprise_data: dict[str, Any],
    enterprise_orgs: list[dict[str, Any]],
    enterprise_members: list[dict[str, Any]],
    saml_provider_data: dict[str, Any] | None,
    external_identity_data: list[dict[str, Any]],
) -> tuple:
    enterprise_resource = enterprise(enterprise_data)
    enterprise_teams_resource = enterprise_teams(ctx, enterprise_data)
    enterprise_roles_resource = enterprise_roles(ctx, enterprise_data)
    enterprise_admin_roles_resource = enterprise_admin_roles(ctx, enterprise_data)
    enterprise_saml_provider_resource = enterprise_saml_provider(saml_provider_data)

    return (
        enterprise_resource,
        enterprise_organizations(enterprise_orgs),
        enterprise_users(enterprise_members),
        enterprise_managed_users(enterprise_members),
        enterprise_teams_resource,
        enterprise_teams_resource | enterprise_team_roles(),
        enterprise_teams_resource | enterprise_team_members(ctx),
        enterprise_teams_resource | enterprise_team_organizations(ctx),
        enterprise_roles_resource,
        enterprise_roles_resource | enterprise_role_users(ctx),
        enterprise_roles_resource | enterprise_role_teams(ctx),
        enterprise_admin_roles_resource,
        enterprise_admins(ctx, enterprise_data),
        enterprise_saml_provider_resource,
        enterprise_external_identities(external_identity_data),
    )


@app.source(name="github", max_table_nesting=0)
def source(
    credentials: Union[
        GithubAppCredentials, GithubTokenCredentials
    ] = dlt.secrets.value,
    host: str = "https://api.github.com",
):
    """DLT source, defines GitHub collection resources and transformers.

    Args:
        credentials (Union[GithubAppCredentials, GithubTokenCredentials]): The GitHub credentials.
        host (str): The base GitHub API URL used for API calls.
    """

    if isinstance(credentials, GithubAppCredentials):
        credentials.api_uri = host

    if bool(credentials.org_name) == bool(credentials.enterprise_name):
        raise ValueError("Specify exactly one of org_name or enterprise_name.")

    def retry_policy(
        response: Optional[requests.Response], exception: Optional[BaseException]
    ) -> bool:
        if response is None:
            return False

        headers = response.headers
        should_retry = (
            True
            if response.status_code in (403, 429)
            and headers.get("x-ratelimit-remaining") == "0"
            else False
        )
        return should_retry

    def github_client(token: str) -> RESTClient:
        return RESTClient(
            base_url=host,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            auth=BearerTokenAuth(token=token),
            paginator=HeaderLinkPaginator(),
            session=requests.Client(retry_condition=retry_policy).session,
        )

    def app_installation_ids_by_org() -> dict[str, int]:
        if not isinstance(credentials, GithubAppCredentials):
            return {}

        installations: dict[str, int] = {}
        for installation in credentials.installations():
            if installation.get("target_type") != "Organization":
                continue
            if installation.get("suspended_at"):
                continue
            account = installation.get("account") or {}
            login = account.get("login") or account.get("slug")
            installation_id = installation.get("id")
            if login and installation_id:
                installations[login] = installation_id
        return installations

    ctx = SourceContext(
        client=github_client(credentials.header),
        org_name=credentials.org_name,
        enterprise_name=credentials.enterprise_name,
        auth_type=credentials.auth(),
    )

    if credentials.enterprise_name:
        enterprise_data, enterprise_orgs = _enterprise_profile_and_orgs(ctx)
        enterprise_members = _enterprise_member_records(ctx, enterprise_data)
        saml_provider_data, external_identity_data = _enterprise_saml_records(ctx)
        ctx.enterprise_node_id = enterprise_data["id"]
        ctx.enterprise_saml_enabled = saml_provider_data is not None

        installation_ids_by_org = app_installation_ids_by_org()
        org_contexts = []
        for org in enterprise_orgs:
            org_login = org["login"]
            org_client = ctx.client
            if isinstance(credentials, GithubAppCredentials):
                installation_id = installation_ids_by_org.get(org_login)
                if not installation_id:
                    continue
                org_client = github_client(
                    credentials.header_for_installation(installation_id)
                )

            org_contexts.append(
                OrgContext(
                    client=org_client,
                    org_name=org_login,
                    org_node_id=org["id"],
                )
            )

        ctx.org_contexts = tuple(org_contexts)

        return (
            *_enterprise_collection_resources(
                ctx,
                enterprise_data,
                enterprise_orgs,
                enterprise_members,
                saml_provider_data,
                external_identity_data,
            ),
            *_org_collection_resources(ctx),
        )

    return _org_collection_resources(ctx)
