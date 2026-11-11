from types import SimpleNamespace
from unittest.mock import MagicMock

import duckdb
import pytest

from openhound_github.enterprise_team_ids import (
    enterprise_database_id,
    enterprise_team_node_id,
)
from openhound_github.lookup import GithubLookup
from openhound_github.models import (
    EnterpriseTeam,
    EnterpriseTeamRole,
    EnterpriseTeamMember,
    EnterpriseTeamOrganization,
)
from openhound_github.models.enterprise_role_team import EnterpriseRoleTeam
from openhound_github.models.projected_enterprise_team import ProjectedEnterpriseTeam
from openhound_github.models.repo_role_assignment import RepoRoleAssignment
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise_team_repo_role_assignments,
    enterprise_resources,
)
from openhound_github.transforms import ensure_optional_input_tables

ENTERPRISE = "E_kgDOAAiv9g"
TEAM_ID = 16703656
NATIVE = "ET_kwDOAAiv9s4A_uCo"


@pytest.mark.parametrize(
    "team_id, expected",
    [
        (16703656, "ET_kwDOAAiv9s4A_uCo"),
        (16701016, "ET_kwDOAAiv9s4A_tZY"),
        (16701018, "ET_kwDOAAiv9s4A_tZa"),
    ],
)
def test_native_id_derivation_matches_observed_github_ids(team_id, expected):
    """Verify derived IDs reproduce native identifiers returned by GitHub."""
    assert enterprise_database_id(ENTERPRISE) == 569334
    assert enterprise_team_node_id(ENTERPRISE, team_id) == expected


@pytest.mark.parametrize("scope", ["not-an-id", "e_kgDOAAiv9g", "E_aGVsbG8", "E_!!!!"])
def test_unknown_scope_encoding_is_not_manufactured(scope):
    """Reject unsupported enterprise encodings instead of inventing team IDs."""
    with pytest.raises(ValueError):
        enterprise_team_node_id(scope, TEAM_ID)


def lookup_with_observations():
    """Create lookup evidence for shared team identities in separate enterprises."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA github")
    ensure_optional_input_tables(con)
    con.execute(
        "INSERT INTO github.enterprise_organizations VALUES ('O_1','org-one',?), ('O_2','org-two',?), ('O_3','other','OTHER_ENTERPRISE')",
        [ENTERPRISE, ENTERPRISE],
    )
    con.execute(
        "INSERT INTO github.projected_enterprise_teams VALUES (?,?,'org-one'), (?,?,'org-two'), (?,'ET_other','other')",
        [TEAM_ID, NATIVE, TEAM_ID, NATIVE, TEAM_ID],
    )
    return GithubLookup(con)


def test_lookup_scopes_native_observations_and_derives_unobserved_teams():
    """Verify enterprise scoping and fallback derivation for unobserved teams."""
    lookup = lookup_with_observations()
    assert lookup.enterprise_team_node_id(ENTERPRISE, TEAM_ID) == NATIVE
    assert lookup.enterprise_team_node_id("OTHER_ENTERPRISE", TEAM_ID) == "ET_other"
    assert lookup.enterprise_team_node_id(ENTERPRISE, 16701016) == "ET_kwDOAAiv9s4A_tZY"


def test_lookup_rejects_conflicting_observations():
    """Reject contradictory native IDs for the same enterprise and numeric team ID."""
    lookup = lookup_with_observations()
    lookup.client.execute(
        "INSERT INTO github.projected_enterprise_teams VALUES (?, 'ET_conflict','org-one')",
        [TEAM_ID],
    )
    with pytest.raises(ValueError, match="Conflicting"):
        lookup.enterprise_team_node_id(ENTERPRISE, TEAM_ID)


def test_native_endpoint_id_takes_precedence_over_encoding_fallback():
    """Prefer a collected native endpoint ID over inferred encoding."""
    lookup = lookup_with_observations()
    lookup.client.execute(
        "INSERT INTO github.enterprise_teams VALUES (123, ?, 'ET_returned')",
        [ENTERPRISE],
    )
    assert lookup.enterprise_team_node_id(ENTERPRISE, 123) == "ET_returned"


def test_all_team_relationships_share_one_native_identity():
    """Verify membership, provisioning, roles, and assignments share one team ID."""
    lookup = lookup_with_observations()
    lookup.enterprise_id = lambda: ENTERPRISE
    context = dict(enterprise_node_id=ENTERPRISE, enterprise_slug="example")
    team = EnterpriseTeam(
        id=TEAM_ID, name="Security", slug="ent:security", group_id="scim-1", **context
    )
    role = EnterpriseTeamRole(
        id=TEAM_ID, name="Security", slug="ent:security", **context
    )
    member = EnterpriseTeamMember(node_id="U_1", team_id=TEAM_ID, **context)
    assignment = EnterpriseRoleTeam(id=TEAM_ID, role_id=12, **context)
    organizations = [
        EnterpriseTeamOrganization(node_id=f"O_{i}", team_id=TEAM_ID, **context)
        for i in [1, 2]
    ]
    for asset in [team, role, member, assignment, *organizations]:
        asset._lookup = lookup
    assert team.as_node.id == NATIVE
    assert role.as_node.properties.team_id == NATIVE
    assert list(role.edges)[0].end.value == NATIVE
    assert list(member.edges)[0].end.value == role.node_id
    assert list(assignment.edges)[0].start.value == NATIVE
    assert list(team.edges)[1].end.value == NATIVE
    for org in organizations:
        edges = list(org.edges)
        assert [(e.kind, e.start.value, e.end.value) for e in edges] == [
            ("GH_AssignedTo", NATIVE, org.node_id)
        ]
    assert NATIVE in team.as_node.properties.query_repositories


def test_organization_observations_emit_no_projected_nodes():
    """Keep organization REST observations as evidence without projected graph nodes."""
    observation = ProjectedEnterpriseTeam(
        node_id=NATIVE,
        id=TEAM_ID,
        name="Security",
        slug="ent:security",
        org_login="org-one",
    )
    assert observation.as_node is None
    assert observation.edges == []


@pytest.mark.parametrize(
    "role, custom_roles, expected_base",
    [
        ("admin", [], None),
        (
            "security-review",
            [
                {
                    "name": "security-review",
                    "id": 12,
                    "base_role": "write",
                    "permissions": ["push_protected_branch"],
                    "org_login": "org-one",
                }
            ],
            "write",
        ),
    ],
)
@pytest.mark.parametrize("dictionary_input", [False, True])
def test_repository_grants_use_org_client_and_native_team_identity(
    role, custom_roles, expected_base, dictionary_input
):
    """Verify paginated built-in and custom grants use the organization client and native ID."""
    client = MagicMock()
    client.paginate.return_value = [
        [{"node_id": "R_1", "name": "repo-one", "role_name": role}],
        [{"node_id": "R_2", "name": "repo-two", "role_name": role}],
    ]
    ctx = SourceContext(
        client=MagicMock(),
        organizations=[SimpleNamespace(org_name="org-one", client=client)],
    )
    assignment = EnterpriseTeamOrganization(
        node_id="O_1",
        org_database_id=42,
        login="org-one",
        team_id=TEAM_ID,
        enterprise_node_id=ENTERPRISE,
        enterprise_slug="example",
    )
    rows = list(
        enterprise_team_repo_role_assignments.__wrapped__(
            assignment.model_dump() if dictionary_input else assignment,
            ctx,
            custom_roles,
        )
    )
    assert len(rows) == 2
    client.paginate.assert_called_once_with(
        f"/organizations/42/team/{TEAM_ID}/repos", params={"per_page": 100}
    )
    ctx.client.paginate.assert_not_called()
    lookup = lookup_with_observations()
    lookup.repository_default_branch_collected = lambda _: False
    for row in rows:
        assert row["base_role"] == expected_base
        model = RepoRoleAssignment(**row)
        model._lookup = lookup
        edge = next(model.edges)
        assert edge.start.value == NATIVE
        assert edge.end.value == f"{row['repo_node_id']}_{role}"


def test_grants_skip_orgs_without_collection_access(caplog):
    """Skip unavailable organization grants without using the enterprise client."""
    ctx = SourceContext(client=MagicMock())
    assignment = EnterpriseTeamOrganization(
        node_id="O_1",
        org_database_id=42,
        login="unavailable",
        team_id=TEAM_ID,
        enterprise_node_id=ENTERPRISE,
        enterprise_slug="example",
    )
    assert (
        list(enterprise_team_repo_role_assignments.__wrapped__(assignment, ctx, []))
        == []
    )
    ctx.client.paginate.assert_not_called()
    assert "organization client or numeric ID unavailable" in caplog.text


def test_source_wires_grants_through_organization_assignments():
    """Verify repository grant collection depends on enterprise-team assignments."""
    resources = {
        r.name: r
        for r in enterprise_resources(
            SourceContext(client=MagicMock(), enterprise_name="example")
        )
    }
    grants = resources["enterprise_team_repo_role_assignments"]
    assert grants.table_name == "repo_role_assignments"
    assert grants._pipe.parent.name == "enterprise_team_organizations"
