from datetime import datetime
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openhound_github.models.app_installation import AppInstallation
from openhound_github.models.app_permissions import (
    APP_PERMISSIONS_BY_SCOPE,
    split_app_permissions,
)
from openhound_github.models.permissions import split_permission_groups
from openhound_github.models.personal_access_token import (
    Owner as PersonalAccessTokenOwner,
    Permissions,
    PersonalAccessToken,
)
from openhound_github.models.personal_access_token_request import (
    Owner as PersonalAccessTokenRequestOwner,
    PersonalAccessTokenRequest,
)


def _lookup() -> MagicMock:
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.org_database_id_for_login.return_value = 1
    return lookup


def test_personal_access_token_permissions_are_normalized_by_scope() -> None:
    token = PersonalAccessToken(
        id=1,
        owner=PersonalAccessTokenOwner(
            login="octocat",
            id=1,
            type="User",
            node_id="U_1",
        ),
        permissions=Permissions(
            organization={"members": "read"},
            repository={"contents": "write", "metadata": "read"},
        ),
        token_id=1,
        token_name="ci-token",
        token_expired=False,
        org_login="acme",
    )
    token._lookup = _lookup()

    properties = token.as_node.properties

    assert properties.permissions_organization == ["members:read"]
    assert properties.permissions_repository == ["contents:write", "metadata:read"]


def test_personal_access_token_request_permissions_are_normalized_by_scope() -> None:
    request = PersonalAccessTokenRequest(
        id=1,
        owner=PersonalAccessTokenRequestOwner(
            login="octocat",
            id=1,
            type="User",
            node_id="U_1",
            site_admin=False,
        ),
        token_name="requested-token",
        token_expired=False,
        permissions={
            "organization": {"members": "read"},
            "repository": {"contents": "write", "metadata": "read"},
        },
        org_login="acme",
    )
    request._lookup = _lookup()

    properties = request.as_node.properties

    assert properties.permissions_organization == ["members:read"]
    assert properties.permissions_repository == ["contents:write", "metadata:read"]


def test_personal_access_token_request_preserves_missing_permission_scope() -> None:
    request = PersonalAccessTokenRequest(
        id=1,
        owner=PersonalAccessTokenRequestOwner(
            login="octocat",
            id=1,
            type="User",
            node_id="U_1",
            site_admin=False,
        ),
        token_name="requested-token",
        token_expired=False,
        permissions={"repository": {"contents": "read"}},
        org_login="acme",
    )
    request._lookup = _lookup()

    properties = request.as_node.properties

    assert properties.permissions_organization == []
    assert properties.permissions_repository == ["contents:read"]


def test_app_installation_permissions_use_normalized_permission_shape() -> None:
    installation = AppInstallation(
        id=1,
        repository_selection="all",
        app_id=42,
        target_type="Organization",
        permissions={"contents": "write", "metadata": "read"},
        created_at=datetime(2026, 1, 1),
        org_login="acme",
    )
    installation._lookup = _lookup()

    assert installation.as_node.properties.permissions_repository == [
        "contents:write",
        "metadata:read",
    ]


@pytest.mark.parametrize(
    "asset_type", [PersonalAccessToken, PersonalAccessTokenRequest]
)
@pytest.mark.parametrize(
    "permissions",
    [
        {},
        {
            "repository": {
                "contents": "write",
                "members": "read",
                "enterprise_people": "read",
                "profile": "write",
                "future_permission": "admin",
            },
        },
        {
            "organization": {"contents": "read"},
            "enterprise": {"enterprise_settings": "write"},
            "account": {"email_addresses": "read"},
            "future_group": {"undocumented_permission": "write"},
        },
    ],
)
def test_pat_permissions_use_app_catalog_without_mutating_input(
    asset_type, permissions
):
    original = deepcopy(permissions)
    asset = asset_type.model_validate(
        {
            "id": 1,
            "owner": {
                "login": "octocat",
                "id": 1,
                "type": "User",
                "node_id": "U_1",
                "site_admin": False,
            },
            "permissions": permissions,
            "token_id": 1,
            "token_name": "token",
            "token_expired": False,
            "org_login": "acme",
        }
    )
    asset._lookup = _lookup()

    properties = asdict(asset.as_node.properties)

    expected = split_app_permissions(
        {key: access for group in original.values() for key, access in group.items()}
    )
    for field, values in expected.items():
        assert properties[field] == values
    assert "organization_permissions" not in properties
    assert "repository_permissions" not in properties
    assert not any(field.startswith("query_") for field in properties)
    assert permissions == original
    stored = (
        asset.permissions.model_dump(exclude_unset=True)
        if isinstance(asset, PersonalAccessToken)
        else asset.permissions
    )
    assert stored == original


@pytest.mark.parametrize(
    "permission,scope",
    [
        (key, scope)
        for scope, keys in APP_PERMISSIONS_BY_SCOPE.items()
        for key in sorted(keys)
    ],
)
def test_grouped_permissions_share_every_app_catalog_entry(permission, scope):
    # Classification follows the shared key catalog, not the original API group.
    result = split_permission_groups({"repository": {permission: "write"}})
    assert result[f"permissions_{scope}"] == [f"{permission}:write"]
    assert sum(len(values) for values in result.values()) == 1


def test_grouped_permissions_preserve_distinct_access_levels_and_legacy_values():
    result = split_permission_groups(
        {
            "repository": {"contents": "write"},
            "organization": {"contents": "read"},
            "legacy": ["contents:write", "unrecognized:admin", "opaque"],
        }
    )
    assert result["permissions_repository"] == ["contents:write", "contents:read"]
    assert result["permissions_unclassified"] == ["unrecognized:admin", "opaque"]


@pytest.mark.parametrize(
    "kind,owner_panel,owner_edge,repository_panel",
    [
        (
            "GH_PersonalAccessToken",
            "owner",
            "GH_HasPersonalAccessToken",
            "repository_scope",
        ),
        (
            "GH_PersonalAccessTokenRequest",
            "requester",
            "GH_HasPersonalAccessTokenRequest",
            "requested_repositories",
        ),
    ],
)
def test_pat_schema_panels_cover_removed_node_queries(
    kind, owner_panel, owner_edge, repository_panel
):
    path = Path(__file__).resolve().parents[1] / "extension/schema.json"
    schema = json.loads(path.read_text())
    panels = next(node for node in schema["node_kinds"] if node["name"] == kind)["info"]
    assert owner_edge in panels[owner_panel]["markdown"]["content"]
    assert (
        "GH_CanAccess]->(:GH_Organization)"
        in panels["organization_scope"]["markdown"]["content"]
    )
    assert (
        "GH_CanAccess|GH_ScopedTo*1..2"
        in panels[repository_panel]["markdown"]["content"]
    )
    for panel in (owner_panel, "organization_scope", repository_panel):
        assert "objectid" in panels[panel]["markdown"]["content"]
