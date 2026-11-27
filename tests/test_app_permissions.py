from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from openhound_github.models.app_installation import App, AppInstallation
from openhound_github.models.app_permissions import (
    APP_PERMISSIONS_BY_SCOPE,
    split_app_permissions,
)


@pytest.mark.parametrize(
    ("permission", "scope"),
    [
        ("contents", "repository"),
        ("administration", "repository"),
        ("metadata", "repository"),
        ("repository_projects", "repository"),
        ("agent_tasks", "repository"),
        ("members", "organization"),
        ("organization_custom_roles", "organization"),
        ("organization_credentials", "organization"),
        ("organization_verifiable_domains", "organization"),
        ("organization_knowledge_bases", "organization"),
        ("organization_models", "organization"),
        ("team_discussions", "organization"),
        ("custom_properties_for_organizations", "organization"),
        ("issue_fields", "organization"),
        ("enterprise_custom_properties_for_organizations", "enterprise"),
        ("enterprise_people", "enterprise"),
        ("enterprise_custom_org_roles", "enterprise"),
        ("enterprise_delegate_policies", "enterprise"),
        ("enterprise_settings", "enterprise"),
        ("enterprise_verifiable_domains", "enterprise"),
        ("enterprise_organization_installation_repositories", "enterprise"),
        ("email_addresses", "account"),
        ("emails", "account"),
        ("git_ssh_keys", "account"),
        ("keys", "account"),
        ("interaction_limits", "account"),
        ("followers", "account"),
        ("copilot_editor_context", "account"),
        ("copilot_messages", "account"),
        ("copilot_requests", "account"),
        ("knowledge_bases", "account"),
        ("user_events", "account"),
        ("user_models", "account"),
        ("future_permission", "unclassified"),
        ("organization_future_permission", "unclassified"),
        ("enterprise_future_permission", "unclassified"),
    ],
)
def test_permission_scope_is_explicit_and_access_level_is_preserved(permission, scope):
    result = split_app_permissions({permission: "admin"})

    assert result[f"permissions_{scope}"] == [f"{permission}:admin"]
    assert sum(len(values) for values in result.values()) == 1


def test_permission_catalog_has_no_conflicting_scope_assignments():
    groups = list(APP_PERMISSIONS_BY_SCOPE.values())
    assert sum(len(group) for group in groups) == len(set().union(*groups))


@pytest.mark.parametrize(
    "asset_type", ["app", "organization_installation", "enterprise_installation"]
)
@pytest.mark.parametrize(
    "permissions",
    [
        {},
        {
            "contents": "write",
            "members": "read",
            "enterprise_people": "read",
            "profile": "write",
            "undocumented_permission": "read",
        },
    ],
)
def test_app_nodes_split_permissions_without_changing_collected_input(
    asset_type, permissions
):
    original = deepcopy(permissions)
    if asset_type == "app":
        asset = App(
            id=7,
            node_id="APP_7",
            slug="example",
            name="Example",
            events=[],
            permissions=permissions,
        )
    else:
        asset = AppInstallation(
            id=42,
            app_id=7,
            permissions=permissions,
            target_type="Enterprise"
            if asset_type == "enterprise_installation"
            else "Organization",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    asset._lookup = MagicMock()
    asset._lookup.enterprise_id.return_value = None

    graph_properties = asdict(asset.as_node.properties)

    assert "permissions" not in graph_properties
    for field, expected in split_app_permissions(original).items():
        assert graph_properties[field] == expected
    assert asset.permissions == original
    assert asset.model_dump()["permissions"] == original
