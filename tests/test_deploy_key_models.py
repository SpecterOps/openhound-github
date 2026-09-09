from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.deploy_key import DeployKey


def _deploy_key(read_only: bool | None) -> DeployKey:
    deploy_key = DeployKey(
        id=7,
        title="ci-key",
        key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ",
        verified=True,
        enabled=True,
        created_at=datetime(2026, 1, 1),
        read_only=read_only,
        last_used=datetime(2026, 1, 2),
        added_by={"login": "alice", "node_id": "USER_1"},
        org_login="acme",
        repository_name="acme/repo",
        repository_node_id="REPO_1",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.user_node_id_for_login.return_value = "USER_1"
    deploy_key._lookup = lookup
    return deploy_key


def test_read_only_deploy_key_surfaces_repository_read_permission() -> None:
    properties = _deploy_key(read_only=True).as_node.properties

    assert properties.name == "acme/repo/ci-key"
    assert properties.repository_permissions == ["contents:read"]
    assert properties.enabled is True
    assert properties.added_by_login == "alice"
    assert properties.added_by_id == "USER_1"


def test_writable_deploy_key_surfaces_repository_write_permission() -> None:
    deploy_key = _deploy_key(read_only=False)

    assert deploy_key.as_node.properties.repository_permissions == ["contents:write"]
    assert [edge.kind for edge in deploy_key.edges] == [
        ek.CONTAINS,
        ek.CAN_ACCESS,
        ek.ADDED_DEPLOY_KEY,
    ]
    assert list(deploy_key.edges)[1].end.value == "REPO_1"


def test_deploy_key_preserves_unknown_repository_permission() -> None:
    properties = _deploy_key(read_only=None).as_node.properties

    assert properties.read_only is None
    assert properties.repository_permissions is None


def test_deploy_key_accepts_string_added_by_login() -> None:
    deploy_key = _deploy_key(read_only=True)
    deploy_key.added_by = "alice"

    properties = deploy_key.as_node.properties

    assert properties.added_by_login == "alice"
    assert properties.added_by_id == "USER_1"
    assert [edge.kind for edge in deploy_key.edges] == [
        ek.CONTAINS,
        ek.CAN_ACCESS,
        ek.ADDED_DEPLOY_KEY,
    ]
    assert list(deploy_key.edges)[2].start.value == "USER_1"
    deploy_key._lookup.user_node_id_for_login.assert_called_with("acme", "alice")


def test_deploy_key_skips_added_by_edge_when_user_was_not_collected() -> None:
    deploy_key = _deploy_key(read_only=True)
    deploy_key._lookup.user_node_id_for_login.return_value = None

    assert deploy_key.as_node.properties.added_by_id is None
    assert [edge.kind for edge in deploy_key.edges] == [ek.CONTAINS, ek.CAN_ACCESS]
