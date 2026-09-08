from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.models.app_installation import AppInstallation
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

    assert properties.organization_permissions == ["members:read"]
    assert properties.repository_permissions == ["contents:write", "metadata:read"]


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

    assert properties.organization_permissions == ["members:read"]
    assert properties.repository_permissions == ["contents:write", "metadata:read"]


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

    assert properties.organization_permissions is None
    assert properties.repository_permissions == ["contents:read"]


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

    assert installation.as_node.properties.permissions == [
        "contents:write",
        "metadata:read",
    ]
