from dataclasses import dataclass, field

from openhound.core.asset import BaseAsset, NodeDef
from openhound.core.models.entries_dataclass import Edge

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHOrganizationProperties(GHNodeProperties):
    """Organization-specific properties and accordion panel queries."""

    login: str = field(
        default="",
        metadata={"description": "The organization's login handle (URL slug)."},
    )
    org_name: str = field(
        default="",
        metadata={
            "description": "The organization's display name (from the `name` field in the GitHub API)."
        },
    )
    description: str | None = field(
        default=None, metadata={"description": "The organization's description."}
    )
    company: str = field(
        default="",
        metadata={"description": "The company associated with the organization."},
    )
    blog: str | None = field(
        default=None, metadata={"description": "The organization's blog URL."}
    )
    location: str | None = field(
        default=None, metadata={"description": "The organization's location."}
    )
    email: str | None = field(
        default=None,
        metadata={"description": "The organization's public email address."},
    )
    is_verified: bool | None = field(
        default=None,
        metadata={
            "description": "Whether the organization's domain is verified by GitHub."
        },
    )
    has_organization_projects: bool | None = field(
        default=None,
        metadata={"description": "Whether the organization has projects enabled."},
    )
    has_repository_projects: bool | None = field(
        default=None,
        metadata={"description": "Whether repository projects are enabled."},
    )
    public_repos: int | None = field(
        default=None,
        metadata={"description": "Number of public repositories in the organization."},
    )
    public_gists: int | None = field(
        default=None, metadata={"description": "Number of public gists."}
    )
    followers: int | None = field(
        default=None,
        metadata={"description": "Number of followers the organization has."},
    )
    following: int | None = field(
        default=None,
        metadata={"description": "Number of accounts the organization is following."},
    )
    html_url: str | None = field(
        default=None,
        metadata={"description": "URL to the organization's GitHub profile page."},
    )
    created_at: str | None = field(
        default=None, metadata={"description": "When the organization was created."}
    )
    updated_at: str | None = field(
        default=None,
        metadata={"description": "When the organization was last updated."},
    )
    type: str | None = field(
        default=None,
        metadata={"description": "The account type (e.g., `Organization`)."},
    )
    total_private_repos: int | None = field(
        default=None, metadata={"description": "Total number of private repositories."}
    )
    owned_private_repos: int | None = field(
        default=None,
        metadata={
            "description": "Number of private repositories owned directly by the organization."
        },
    )
    private_gists: int | None = field(
        default=None, metadata={"description": "Number of private gists."}
    )
    collaborators: int | None = field(
        default=None,
        metadata={
            "description": "Number of outside collaborators across the organization."
        },
    )
    environment_name: str = field(
        default="",
        metadata={"description": "The name of the environment (GitHub organization)."},
    )
    default_repository_permission: str | None = field(
        default=None,
        metadata={
            "description": "Default permission level granted to members on all repositories (e.g., `read`, `write`, `admin`, `none`). Used to associate the Members org role with the appropriate `all_repo_*` role node."
        },
    )
    members_can_create_repositories: bool | None = field(
        default=None,
        metadata={"description": "Whether members can create repositories."},
    )
    two_factor_requirement_enabled: bool | None = field(
        default=None,
        metadata={
            "description": "Whether two-factor authentication is required for all members."
        },
    )
    members_can_create_public_repositories: bool | None = field(
        default=None,
        metadata={"description": "Whether members can create public repositories."},
    )
    members_can_create_private_repositories: bool | None = field(
        default=None,
        metadata={"description": "Whether members can create private repositories."},
    )
    members_can_create_internal_repositories: bool | None = field(
        default=None,
        metadata={"description": "Whether members can create internal repositories."},
    )
    members_can_create_pages: bool | None = field(
        default=None,
        metadata={"description": "Whether members can create GitHub Pages sites."},
    )
    members_can_fork_private_repositories: bool | None = field(
        default=None,
        metadata={"description": "Whether members can fork private repositories."},
    )
    web_commit_signoff_required: bool | None = field(
        default=None,
        metadata={"description": "Whether web-based commits require sign-off."},
    )
    deploy_keys_enabled_for_repositories: bool | None = field(
        default=None, metadata={"description": "Which repositories allow deploy keys."}
    )
    members_can_delete_repositories: bool | None = field(
        default=None,
        metadata={"description": "Whether members can delete repositories."},
    )
    members_can_change_repo_visibility: bool | None = field(
        default=None,
        metadata={"description": "Whether members can change repository visibility."},
    )
    members_can_invite_outside_collaborators: bool | None = field(
        default=None,
        metadata={"description": "Whether members can invite outside collaborators."},
    )
    members_can_delete_issues: bool | None = field(
        default=None, metadata={"description": "Whether members can delete issues."}
    )
    display_commenter_full_name_setting_enabled: bool | None = field(
        default=None,
        metadata={"description": "Whether commenter full names are displayed."},
    )
    readers_can_create_discussions: bool | None = field(
        default=None,
        metadata={"description": "Whether readers can create discussions."},
    )
    members_can_create_teams: bool | None = field(
        default=None, metadata={"description": "Whether members can create teams."}
    )
    members_can_view_dependency_insights: bool | None = field(
        default=None,
        metadata={"description": "Whether members can view dependency insights."},
    )
    default_repository_branch: str | None = field(
        default=None,
        metadata={"description": "The default branch name for new repositories."},
    )
    members_can_create_public_pages: bool | None = field(
        default=None,
        metadata={
            "description": "Whether members can create public GitHub Pages sites."
        },
    )
    members_can_create_private_pages: bool | None = field(
        default=None,
        metadata={
            "description": "Whether members can create private GitHub Pages sites."
        },
    )
    advanced_security_enabled_for_new_repositories: bool | None = field(
        default=None,
        metadata={
            "description": "Whether GitHub Advanced Security is automatically enabled for new repositories."
        },
    )
    dependabot_alerts_enabled_for_new_repositories: bool | None = field(
        default=None,
        metadata={
            "description": "Whether Dependabot alerts are enabled for new repositories."
        },
    )
    dependabot_security_updates_enabled_for_new_repositories: bool | None = field(
        default=None,
        metadata={
            "description": "Whether Dependabot security updates are enabled for new repositories."
        },
    )
    dependency_graph_enabled_for_new_repositories: bool | None = field(
        default=None,
        metadata={
            "description": "Whether the dependency graph is enabled for new repositories."
        },
    )
    secret_scanning_enabled_for_new_repositories: bool | None = field(
        default=None,
        metadata={
            "description": "Whether secret scanning is enabled for new repositories."
        },
    )
    secret_scanning_push_protection_enabled_for_new_repositories: bool | None = field(
        default=None,
        metadata={
            "description": "Whether secret scanning push protection is enabled for new repositories."
        },
    )
    secret_scanning_push_protection_custom_link_enabled: bool | None = field(
        default=None,
        metadata={
            "description": "Whether a custom link is enabled for secret scanning push protection."
        },
    )
    secret_scanning_push_protection_custom_link: str = field(
        default="",
        metadata={
            "description": "The custom link for secret scanning push protection."
        },
    )
    secret_scanning_validity_checks_enabled: bool | None = field(
        default=None,
        metadata={
            "description": "Whether secret scanning validity checks are enabled."
        },
    )
    actions_enabled_repositories: str | None = field(
        default=None,
        metadata={
            "description": "Which repositories have GitHub Actions enabled: `all`, `selected`, or `none`."
        },
    )
    actions_allowed_actions: str | None = field(
        default=None,
        metadata={
            "description": "Which Actions are allowed to run: `all`, `local_only`, or `selected`."
        },
    )
    actions_sha_pinning_required: bool | None = field(
        default=None,
        metadata={"description": "Whether SHA pinning is required for GitHub Actions."},
    )
    default_workflow_permissions: str | None = None
    can_approve_pull_request_reviews: bool | None = None
    query_organization_roles: str = ""
    query_users: str = ""
    query_teams: str = ""
    query_repositories: str = ""
    query_personal_access_tokens: str = ""
    query_secret_scanning_alerts: str = ""
    query_identity_provider: str = ""
    query_app_installations: str = ""
    query_organization_secrets: str = ""
    collected: bool = True


@app.asset(
    node=NodeDef(
        kind=nk.ORGANIZATION,
        description="GitHub Organization",
        icon="building",
        properties=GHOrganizationProperties,
    ),
)
class Organization(BaseAsset):
    """One record from the `organizations` DLT table → one GH_Organization node."""

    node_id: str
    login: str
    name: str | None = None
    description: str | None = None
    company: str | None = None
    blog: str | None = None
    location: str | None = None
    email: str | None = None
    is_verified: bool | None = None
    has_organization_projects: bool | None = None
    has_repository_projects: bool | None = None
    public_repos: int | None = None
    public_gists: int | None = None
    followers: int | None = None
    following: int | None = None
    html_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    type: str | None = None
    total_private_repos: int | None = None
    owned_private_repos: int | None = None
    private_gists: int | None = None
    collaborators: int | None = None
    default_repository_permission: str | None = None
    members_can_create_repositories: bool | None = None
    two_factor_requirement_enabled: bool | None = None
    members_can_create_public_repositories: bool | None = None
    members_can_create_private_repositories: bool | None = None
    members_can_create_internal_repositories: bool | None = None
    members_can_create_pages: bool | None = None
    members_can_fork_private_repositories: bool | None = None
    web_commit_signoff_required: bool | None = None
    deploy_keys_enabled_for_repositories: bool | None = None
    members_can_delete_repositories: bool | None = None
    members_can_change_repo_visibility: bool | None = None
    members_can_invite_outside_collaborators: bool | None = None
    members_can_delete_issues: bool | None = None
    display_commenter_full_name_setting_enabled: bool | None = None
    readers_can_create_discussions: bool | None = None
    members_can_create_teams: bool | None = None
    members_can_view_dependency_insights: bool | None = None
    default_repository_branch: str | None = None
    members_can_create_public_pages: bool | None = None
    members_can_create_private_pages: bool | None = None
    advanced_security_enabled_for_new_repositories: bool | None = None
    dependabot_alerts_enabled_for_new_repositories: bool | None = None
    dependabot_security_updates_enabled_for_new_repositories: bool | None = None
    dependency_graph_enabled_for_new_repositories: bool | None = None
    secret_scanning_enabled_for_new_repositories: bool | None = None
    secret_scanning_push_protection_enabled_for_new_repositories: bool | None = None
    secret_scanning_push_protection_custom_link_enabled: bool | None = None
    secret_scanning_push_protection_custom_link: str | None = None
    secret_scanning_validity_checks_enabled: bool | None = None
    actions_enabled_repositories: str | None = None
    actions_allowed_actions: str | None = None
    actions_sha_pinning_required: bool | None = None
    default_workflow_permissions: str | None = None
    can_approve_pull_request_reviews: bool | None = None

    @property
    def as_node(self) -> GHNode:
        oid = self.node_id
        return GHNode(
            kinds=["GH_Organization"],
            properties=GHOrganizationProperties(
                name=self.login,
                displayname=self.name or self.login,
                node_id=oid,
                login=self.login,
                org_name=self.name or "",
                description=self.description,
                company=self.company or "",
                blog=self.blog,
                location=self.location,
                email=self.email,
                is_verified=self.is_verified,
                has_organization_projects=self.has_organization_projects,
                has_repository_projects=self.has_repository_projects,
                public_repos=self.public_repos,
                public_gists=self.public_gists,
                followers=self.followers,
                following=self.following,
                html_url=self.html_url,
                created_at=self.created_at,
                updated_at=self.updated_at,
                type=self.type,
                total_private_repos=self.total_private_repos,
                owned_private_repos=self.owned_private_repos,
                private_gists=self.private_gists,
                collaborators=self.collaborators,
                environment_name=self.login,
                environmentid=oid,
                default_repository_permission=self.default_repository_permission,
                members_can_create_repositories=self.members_can_create_repositories,
                two_factor_requirement_enabled=self.two_factor_requirement_enabled,
                members_can_create_public_repositories=self.members_can_create_public_repositories,
                members_can_create_private_repositories=self.members_can_create_private_repositories,
                members_can_create_internal_repositories=self.members_can_create_internal_repositories,
                members_can_create_pages=self.members_can_create_pages,
                members_can_fork_private_repositories=self.members_can_fork_private_repositories,
                web_commit_signoff_required=self.web_commit_signoff_required,
                deploy_keys_enabled_for_repositories=self.deploy_keys_enabled_for_repositories,
                members_can_delete_repositories=self.members_can_delete_repositories,
                members_can_change_repo_visibility=self.members_can_change_repo_visibility,
                members_can_invite_outside_collaborators=self.members_can_invite_outside_collaborators,
                members_can_delete_issues=self.members_can_delete_issues,
                display_commenter_full_name_setting_enabled=self.display_commenter_full_name_setting_enabled,
                readers_can_create_discussions=self.readers_can_create_discussions,
                members_can_create_teams=self.members_can_create_teams,
                members_can_view_dependency_insights=self.members_can_view_dependency_insights,
                default_repository_branch=self.default_repository_branch,
                members_can_create_public_pages=self.members_can_create_public_pages,
                members_can_create_private_pages=self.members_can_create_private_pages,
                advanced_security_enabled_for_new_repositories=self.advanced_security_enabled_for_new_repositories,
                dependabot_alerts_enabled_for_new_repositories=self.dependabot_alerts_enabled_for_new_repositories,
                dependabot_security_updates_enabled_for_new_repositories=self.dependabot_security_updates_enabled_for_new_repositories,
                dependency_graph_enabled_for_new_repositories=self.dependency_graph_enabled_for_new_repositories,
                secret_scanning_enabled_for_new_repositories=self.secret_scanning_enabled_for_new_repositories,
                secret_scanning_push_protection_enabled_for_new_repositories=self.secret_scanning_push_protection_enabled_for_new_repositories,
                secret_scanning_push_protection_custom_link_enabled=self.secret_scanning_push_protection_custom_link_enabled,
                secret_scanning_push_protection_custom_link=self.secret_scanning_push_protection_custom_link
                or "",
                secret_scanning_validity_checks_enabled=self.secret_scanning_validity_checks_enabled,
                actions_enabled_repositories=self.actions_enabled_repositories,
                actions_allowed_actions=self.actions_allowed_actions,
                actions_sha_pinning_required=self.actions_sha_pinning_required,
                default_workflow_permissions=self.default_workflow_permissions,
                can_approve_pull_request_reviews=self.can_approve_pull_request_reviews,
                query_organization_roles=f"MATCH (:GH_Organization {{node_id:'{oid}'}})-[:GH_Contains]->(n:GH_OrgRole) RETURN n",
                query_users=f"MATCH (n:GH_User {{environmentid:'{oid}'}}) RETURN n",
                query_teams=f"MATCH (n:GH_Team {{environmentid:'{oid}'}}) RETURN n",
                query_repositories=f"MATCH (n:GH_Repository {{environmentid:'{oid}'}}) RETURN n",
                query_personal_access_tokens=f"MATCH p=(:GH_Organization {{node_id: '{oid}'}})-[:GH_Contains]->(token) WHERE token:GH_PersonalAccessToken OR token:GH_PersonalAccessTokenRequest RETURN p",
                query_secret_scanning_alerts=f"MATCH p=(:GH_Organization {{node_id: '{oid}'}})-[:GH_Contains]->(alert:GH_SecretScanningAlert) RETURN p",
                query_identity_provider=f"MATCH p=(OIP:GH_SamlIdentityProvider)-[:GH_HasExternalIdentity]->(EI:GH_ExternalIdentity) MATCH p1=(OIP)<-[:GH_HasSamlIdentityProvider]-(:GH_Organization {{node_id:'{oid}'}}) MATCH p2=(EI)-[:GH_MapsToUser]->() RETURN p,p1,p2",
                query_app_installations=f"MATCH p=(:GH_Organization {{node_id:'{oid}'}})-[:GH_Contains]->(:GH_AppInstallation) RETURN p",
                query_organization_secrets=f"MATCH p=(:GH_Organization {{node_id: '{oid}'}})-[:GH_Contains]->(secret:GH_OrganizationSecret) RETURN p",
            ),
        )

    @property
    def edges(self) -> list[Edge]:
        # Edges TO the org are emitted by the assets that own those relationships
        # (e.g. OrgRoleAsset emits GH_Contains from org→role).
        return []
