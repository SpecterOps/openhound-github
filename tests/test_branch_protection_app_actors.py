from unittest.mock import Mock

import duckdb
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.branch_protection_rule import Actor, BranchProtectionRule
from openhound_github.models.repository import RepositoryQL
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    branch_protection_rules,
)
from openhound_github.transforms import ensure_app_installation_input_tables


@pytest.mark.parametrize("allowance", ["bypassPullRequestAllowances", "pushAllowances"])
def test_collection_preserves_app_user_and_team_allowance_actors(allowance):
    actors = [
        {"__typename": "App", "id": "APP_1", "slug": "release-app"},
        {"__typename": "User", "id": "USER_1", "login": "alice"},
        {"__typename": "Team", "id": "TEAM_1", "slug": "release-team"},
    ]
    rule = {
        "id": "RULE_1",
        "pattern": "main",
        **dict.fromkeys(
            [
                "isAdminEnforced",
                "lockBranch",
                "blocksCreations",
                "requiresApprovingReviews",
                "requiresCodeOwnerReviews",
                "requireLastPushApproval",
                "restrictsPushes",
                "requiresStatusChecks",
                "requiresStrictStatusChecks",
                "dismissesStaleReviews",
                "allowsForcePushes",
                "allowsDeletions",
            ],
            False,
        ),
        allowance: {"nodes": [{"actor": a} for a in actors] + [{"actor": None}]},
    }
    client = Mock()
    client.post.return_value.json.return_value = {"data": {"nodes": [rule]}}
    ctx = SourceContext(
        client=client, organizations=[OrgContext(client=client, org_name="acme")]
    )
    repository = RepositoryQL(
        id="REPO_1",
        name="repo",
        org_login="acme",
        refs={
            "nodes": [
                {
                    "id": "BRANCH_1",
                    "name": "main",
                    "target": {"oid": "abc123"},
                    "branchProtectionRule": {"id": "RULE_1"},
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    )

    rows = list(branch_protection_rules.__wrapped__(repository, ctx))
    collected = BranchProtectionRule.model_validate(rows[0])

    # Both allowance connections must request App identity and actor type.
    query = client.post.call_args.kwargs["json"]["query"]
    for connection in ("bypassPullRequestAllowances", "pushAllowances"):
        actor_selection = query.split(f"{connection}(first: 100)", 1)[1].split(
            "... on Team", 1
        )[0]
        assert "__typename" in actor_selection
        assert "... on App { id slug }" in actor_selection
        assert "... on User { id login }" in actor_selection

    field = (
        collected.bypass_pull_request_allowances
        if allowance == "bypassPullRequestAllowances"
        else collected.push_allowances
    )
    assert [
        node.actor.model_dump(by_alias=True, exclude_none=True) for node in field.nodes
    ] == actors
    assert collected.repository_node_id == "REPO_1"
    # Normalized collected records retain the type when read back for conversion.
    restored = BranchProtectionRule.model_validate(collected.model_dump())
    assert restored == collected


@pytest.mark.parametrize(
    "identity", [{"id": "U_1", "login": "alice"}, {"id": "T_1", "slug": "team"}]
)
def test_legacy_allowance_actor_does_not_require_typename(identity):
    actor = Actor.model_validate(identity)

    assert actor.id == identity["id"]
    assert actor.typename is None


@pytest.mark.parametrize(
    ("selection", "org", "suspended", "grant", "expected"),
    [
        ("all", "acme", None, False, True),
        ("selected", "acme", None, True, True),
        ("selected", "acme", None, False, False),
        ("all", "other-org", None, False, False),
        ("all", "acme", "2026-11-20", False, False),
    ],
)
def test_app_exception_edges_resolve_only_installations_with_access(
    selection, org, suspended, grant, expected
):
    actor = {"__typename": "App", "id": "APP_1", "slug": "release-app"}
    mixed_actors = {
        "nodes": [
            {"actor": actor},
            {"actor": actor},
            {"actor": {"__typename": "Team", "id": "TEAM_1", "slug": "release-app"}},
            {"actor": {"__typename": "User", "id": "USER_1", "login": "alice"}},
            {
                "actor": {
                    "__typename": "App",
                    "id": "MISSING_APP",
                    "slug": "missing-app",
                }
            },
            {"actor": {"__typename": "App", "id": "NO_SLUG"}},
            {"actor": {}},
        ]
    }
    rule = BranchProtectionRule(
        id="RULE_1",
        pattern="main",
        org_login="acme",
        repository_node_id="REPO_1",
        repository_name="repo",
        isAdminEnforced=True,
        lockBranch=False,
        blocksCreations=False,
        requiresApprovingReviews=True,
        requiresCodeOwnerReviews=False,
        requireLastPushApproval=False,
        restrictsPushes=True,
        requiresStatusChecks=False,
        requiresStrictStatusChecks=False,
        dismissesStaleReviews=False,
        allowsForcePushes=False,
        allowsDeletions=False,
        bypassPullRequestAllowances=mixed_actors,
        pushAllowances=mixed_actors,
    )
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA github")
        ensure_app_installation_input_tables(con)
        con.execute("INSERT INTO github.repositories VALUES ('REPO_1', 101, 'acme')")
        # No contents grant is required to represent the configured exceptions.
        con.execute(
            "INSERT INTO github.app_installations "
            "(id, app_slug, target_type, environment_slug, repository_selection, suspended_at) "
            "VALUES (42, 'release-app', 'Organization', ?, ?, ?)",
            [org, selection, suspended],
        )
        if grant:
            con.execute(
                "INSERT INTO github.app_installation_repo_access VALUES ('GH_AppInstallation_42', 101, 'acme')"
            )
        rule._lookup = GithubLookup(con)
        edges = list(rule.edges)
        if expected:
            for excluded, remaining_kind in (
                ("bypass_pull_request_allowances", ek.RESTRICTIONS_CAN_PUSH),
                ("push_allowances", ek.BYPASS_PULL_REQUEST_ALLOWANCES),
            ):
                single_allowance = rule.model_copy(update={excluded: None})
                assert [e.kind for e in single_allowance.edges] == [
                    ek.CONTAINS,
                    remaining_kind,
                ]

    assert edges[0].kind == ek.CONTAINS
    assert edges[0].start.value == "REPO_1"
    exceptions = edges[1:]
    assert {e.kind for e in exceptions} == (
        {ek.BYPASS_PULL_REQUEST_ALLOWANCES, ek.RESTRICTIONS_CAN_PUSH}
        if expected
        else set()
    )
    assert len(exceptions) == (2 if expected else 0)
    assert all(
        e.start.value == "GH_AppInstallation_42" and e.end.value == "RULE_1"
        for e in exceptions
    )
    assert all(e.properties.traversable is False for e in exceptions)
