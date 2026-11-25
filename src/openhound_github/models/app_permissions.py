"""Classify flat GitHub App permissions without inferring scope from installation targets.

Catalog snapshot: 2026-11-24. Sources:
https://github.com/github/docs/tree/main/src/github-apps/data
https://github.com/github/rest-api-description/blob/main/descriptions/api.github.com/api.github.com.json
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#permissions
https://docs.github.com/en/rest/agent-tasks/agent-tasks

The documentation catalog supplies scope labels; the app-permissions API schema
also covers keys without documented REST endpoints and account-key aliases.
Legacy enterprise keys remain supported for existing collected records.
Additional enterprise and organization keys observed in collector test data
are explicitly classified following review of their resource scopes.
Unknown keys are preserved separately rather than assigned by prefix.
"""

APP_PERMISSIONS_BY_SCOPE: dict[str, frozenset[str]] = {
    "repository": frozenset(
        {
            "actions",
            "actions_variables",
            "administration",
            "agent_secrets",
            "agent_tasks",
            "agent_variables",
            "artifact_metadata",
            "attestations",
            "checks",
            "code_quality",
            "codespaces",
            "codespaces_lifecycle_admin",
            "codespaces_metadata",
            "codespaces_secrets",
            "contents",
            "copilot_agent_settings",
            "dependabot_secrets",
            "deployments",
            "discussions",
            "environments",
            "installation_repositories",
            "issues",
            "merge_queues",
            "metadata",
            "packages",
            "pages",
            "pull_requests",
            "repo_secret_scanning_dismissal_requests",
            "repository_advisories",
            "repository_creation",
            "repository_custom_properties",
            "repository_hooks",
            "repository_license_policy",
            "repository_projects",
            "secret_scanning_alerts",
            "secret_scanning_bypass_requests",
            "secrets",
            "security_events",
            "single_file",
            "statuses",
            "vulnerability_alerts",
            "workflows",
        }
    ),
    "organization": frozenset(
        {
            "custom_properties_for_organizations",
            "issue_fields",
            "issue_types",
            "members",
            "org_copilot_content_exclusion",
            "organization_actions_variables",
            "organization_administration",
            "organization_agent_secrets",
            "organization_agent_variables",
            "organization_announcement_banners",
            "organization_api_insights",
            "organization_campaigns",
            "organization_code_scanning_dismissal_requests",
            "organization_codespaces",
            "organization_codespaces_secrets",
            "organization_codespaces_settings",
            "organization_copilot_agent_settings",
            "organization_copilot_metrics",
            "organization_copilot_requests",
            "organization_copilot_seat_management",
            "organization_copilot_spaces",
            "organization_credentials",
            "organization_custom_org_roles",
            "organization_custom_properties",
            "organization_custom_roles",
            "organization_dependabot_dismissal_requests",
            "organization_dependabot_secrets",
            "organization_events",
            "organization_external_properties_for_repos",
            "organization_hooks",
            "organization_knowledge_bases",
            "organization_models",
            "organization_network_configurations",
            "organization_packages",
            "organization_personal_access_token_requests",
            "organization_personal_access_tokens",
            "organization_plan",
            "organization_private_registries",
            "organization_projects",
            "organization_runner_custom_images",
            "organization_secret_scanning_bypass_requests",
            "organization_secrets",
            "organization_self_hosted_runners",
            "organization_user_blocking",
            "organization_verifiable_domains",
            "secret_scanning_dismissal_requests",
            "team_discussions",
        }
    ),
    "enterprise": frozenset(
        {
            "enterprise_access_restrictions",
            "enterprise_ai_controls",
            "enterprise_billing",
            "enterprise_bypass_requests",
            "enterprise_copilot_licenses",
            "enterprise_copilot_metrics",
            "enterprise_copilot_usage",
            "enterprise_credentials",
            "enterprise_custom_enterprise_roles",
            "enterprise_custom_org_roles",
            "enterprise_custom_properties",
            "enterprise_custom_properties_for_organizations",
            "enterprise_delegate_policies",
            "enterprise_innersource_vulnerabilities",
            "enterprise_license_policy",
            "enterprise_licensing",
            "enterprise_organization_installation_repositories",
            "enterprise_organization_installations",
            "enterprise_organizations",
            "enterprise_people",
            "enterprise_ref_rules",
            "enterprise_scim",
            "enterprise_security_products",
            "enterprise_settings",
            "enterprise_sso",
            "enterprise_teams",
            "enterprise_verifiable_domains",
        }
    ),
    "account": frozenset(
        {
            "blocking",
            "codespaces_user_secrets",
            "copilot_editor_context",
            "copilot_messages",
            "copilot_requests",
            "email_addresses",
            "emails",
            "followers",
            "gists",
            "git_signing_ssh_public_keys",
            "git_ssh_keys",
            "gpg_keys",
            "interaction_limits",
            "keys",
            "knowledge_bases",
            "plan",
            "private_repository_invitations",
            "profile",
            "starring",
            "user_events",
            "user_issue_fields",
            "user_issue_types",
            "user_models",
            "watching",
        }
    ),
}

_SCOPE_FOR_PERMISSION = {
    permission: scope
    for scope, permissions in APP_PERMISSIONS_BY_SCOPE.items()
    for permission in permissions
}


def split_app_permissions(permissions: dict[str, str]) -> dict[str, list[str]]:
    """Preserve each requested/granted declaration in exactly one graph property."""
    result: dict[str, list[str]] = {
        f"permissions_{scope}": []
        for scope in (*APP_PERMISSIONS_BY_SCOPE, "unclassified")
    }
    for permission, access in permissions.items():
        scope = _SCOPE_FOR_PERMISSION.get(permission, "unclassified")
        result[f"permissions_{scope}"].append(f"{permission}:{access}")
    return result
