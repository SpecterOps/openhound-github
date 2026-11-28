from unittest.mock import MagicMock
from role_id_helpers import configure_role_ids, org_role_id
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.models.org_role_member import OrgRoleMember


@pytest.mark.parametrize("assignment", ["direct", "mixed", "indirect", None])
def test_org_role_members_only_emit_direct_assignment_edges(assignment):
    record = {
        "id": 1,
        "node_id": "U_1",
        "login": "alice",
        "type": "User",
        "site_admin": False,
        "org_role_id": 42,
        "org_role_name": "app_manager",
        "org_node_id": "O_1",
        "org_login": "acme",
    }
    if assignment is not None:
        record["assignment"] = assignment
    member = OrgRoleMember.model_validate(record)
    member._lookup = configure_role_ids(MagicMock())
    assert member.model_dump()["assignment"] == assignment

    edges = list(member.edges)

    if assignment == "indirect":
        assert edges == []
    else:
        assert len(edges) == 1
        assert edges[0].kind == ek.HAS_ROLE
        assert edges[0].start.value == "U_1"
        assert edges[0].end.value == org_role_id("app_manager", 42)
        assert edges[0].properties.traversable
