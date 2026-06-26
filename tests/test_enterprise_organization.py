"""
Tests for EnterpriseOrganization.as_node `collected` resolution.

An organization discovered via the enterprise is a stub node. Its `collected`
flag must be derived from the organizations lookup table so that it agrees with
the full Organization node regardless of ingestion order:

    - explicitly collected org (present in lookup) -> collected=True
    - enterprise-only discovered org (absent)       -> collected=False
"""
from unittest.mock import MagicMock

from openhound_github.models import EnterpriseOrganization


def _make_org(node_id: str = "ORG_NODE_1", login: str = "acme") -> EnterpriseOrganization:
    org = EnterpriseOrganization(
        id=node_id,
        login=login,
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="acme-enterprise",
    )
    return org


def test_collected_true_when_org_in_lookup() -> None:
    """An org present in the organizations lookup is marked collected=True."""
    org = _make_org(node_id="ORG_NODE_1", login="acme")
    lookup = MagicMock()
    lookup.org_login_for_id.return_value = "acme"
    org._lookup = lookup

    node = org.as_node

    assert node.properties.collected is True
    lookup.org_login_for_id.assert_called_once_with("ORG_NODE_1")


def test_collected_false_when_org_not_in_lookup() -> None:
    """An enterprise-only discovered org (absent from lookup) is collected=False."""
    org = _make_org(node_id="ORG_NODE_2", login="beta")
    lookup = MagicMock()
    lookup.org_login_for_id.return_value = None
    org._lookup = lookup

    node = org.as_node

    assert node.properties.collected is False
    lookup.org_login_for_id.assert_called_once_with("ORG_NODE_2")


def test_collected_resolved_per_node_id_in_multi_org_enterprise() -> None:
    """Each stub resolves `collected` against its own node_id independently."""
    collected_ids = {"ORG_NODE_COLLECTED"}

    def fake_lookup(node_id: str):
        return "login" if node_id in collected_ids else None

    lookup = MagicMock()
    lookup.org_login_for_id.side_effect = fake_lookup

    collected_org = _make_org(node_id="ORG_NODE_COLLECTED", login="collected")
    collected_org._lookup = lookup

    stub_org = _make_org(node_id="ORG_NODE_STUB", login="stub")
    stub_org._lookup = lookup

    assert collected_org.as_node.properties.collected is True
    assert stub_org.as_node.properties.collected is False
