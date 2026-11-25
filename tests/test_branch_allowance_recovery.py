from copy import deepcopy
from unittest.mock import Mock

import pytest
import requests

from openhound_github.models.branch_protection_rule import Actor
from openhound_github.models.repository import RepositoryQL
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    branch_protection_rules,
)


USER = {"__typename": "User", "id": "USER_GRAPHQL", "login": "alice"}
TEAM = {"__typename": "Team", "id": "TEAM_1", "slug": "release"}
APP = {"__typename": "App", "id": "APP_1", "slug": "release"}


def _rest_allowances():
    return {
        "users": [{"node_id": "USER_REST", "login": "Alice"}],
        "teams": [{"node_id": "TEAM_1", "slug": "release"}],
        "apps": [{"node_id": "APP_1", "id": 7, "slug": "release"}],
    }


def _rule(rule_id="RULE_1", field="pushAllowances"):
    return {
        "id": rule_id,
        "pattern": "release/*",
        "requiresApprovingReviews": True,
        "pushAllowances": {"nodes": []},
        "bypassPullRequestAllowances": {"nodes": []},
        field: {"nodes": [{"actor": USER}, {"actor": TEAM}, {"actor": None}]},
    }


def _harness(rules, errors=None, branches=None):
    rest = Mock()
    graphql = Mock()
    response = {"data": {"nodes": rules}}
    if errors:
        response["errors"] = errors
    graphql.post.return_value.json.return_value = response
    rest.get.return_value.json.return_value = {
        "restrictions": _rest_allowances(),
        "required_pull_request_reviews": {
            "bypass_pull_request_allowances": _rest_allowances()
        },
    }
    ctx = SourceContext(
        client=Mock(),
        organizations=[
            OrgContext(client=rest, graphql_client=graphql, org_name="acme")
        ],
    )
    repository = RepositoryQL(
        id="REPO_1",
        name="repo",
        org_login="acme",
        refs={
            "nodes": [
                {
                    "id": f"BRANCH_{index}",
                    "name": name,
                    "target": {"oid": "sha"},
                    "branchProtectionRule": {"id": rule_id},
                }
                for index, (name, rule_id) in enumerate(
                    branches or [("release/production", "RULE_1")]
                )
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    )
    return repository, ctx, rest, graphql


def _error(field="pushAllowances", index=0):
    return {"type": "INTERNAL", "path": ["nodes", index, field, "nodes", 2, "actor"]}


@pytest.mark.parametrize("field", ["pushAllowances", "bypassPullRequestAllowances"])
def test_actor_error_recovers_rest_app_and_preserves_graphql_identities(field):
    repository, ctx, rest, graphql = _harness([_rule(field=field)], [_error(field)])

    rows = list(branch_protection_rules.__wrapped__(repository, ctx))

    assert [node["actor"] for node in rows[0][field]["nodes"]] == [USER, TEAM, APP]
    assert rows[0]["requiresApprovingReviews"] is True
    assert rows[0]["repository_node_id"] == "REPO_1"
    # REST node_id is a graph ID; REST's numeric id must not be used as one.
    assert Actor.model_validate(rows[0][field]["nodes"][-1]["actor"]).id == "APP_1"
    rest.get.assert_called_once_with(
        "/repos/acme/repo/branches/release%2Fproduction/protection"
    )
    graphql.get.assert_not_called()
    ctx.client.get.assert_not_called()


def test_successful_graphql_actors_require_no_rest_request():
    rule = _rule()
    rule["pushAllowances"]["nodes"] = [{"actor": actor} for actor in (USER, TEAM, APP)]
    repository, ctx, rest, _ = _harness([rule])

    row = list(branch_protection_rules.__wrapped__(repository, ctx))[0]

    assert [n["actor"] for n in row["pushAllowances"]["nodes"]] == [USER, TEAM, APP]
    rest.get.assert_not_called()


def test_null_actor_without_graphql_error_retains_existing_filter_behavior():
    repository, ctx, rest, _ = _harness([_rule()])

    row = list(branch_protection_rules.__wrapped__(repository, ctx))[0]

    assert [n["actor"] for n in row["pushAllowances"]["nodes"]] == [USER, TEAM]
    rest.get.assert_not_called()


def test_two_failed_connections_and_shared_branches_need_one_rest_request():
    rule = _rule()
    rule["bypassPullRequestAllowances"] = deepcopy(rule["pushAllowances"])
    repository, ctx, rest, _ = _harness(
        [rule],
        [_error(), _error("bypassPullRequestAllowances")],
        branches=[("release/production", "RULE_1"), ("main", "RULE_1")],
    )

    rows = list(branch_protection_rules.__wrapped__(repository, ctx))

    assert len(rows) == 1
    assert rows[0]["pushAllowances"] == rows[0]["bypassPullRequestAllowances"]
    assert len(rows[0]["pushAllowances"]["nodes"]) == 3
    rest.get.assert_called_once()


def test_graphql_error_path_recovers_only_the_affected_rule():
    first = _rule()
    first["pushAllowances"]["nodes"] = [{"actor": TEAM}]
    repository, ctx, rest, _ = _harness(
        [first, _rule("RULE_2")],
        [_error(index=1)],
        branches=[("main", "RULE_1"), ("release/production", "RULE_2")],
    )

    rows = list(branch_protection_rules.__wrapped__(repository, ctx))

    assert rows[0]["pushAllowances"]["nodes"] == [{"actor": TEAM}]
    assert rows[1]["pushAllowances"]["nodes"][-1]["actor"] == APP
    rest.get.assert_called_once_with(
        "/repos/acme/repo/branches/release%2Fproduction/protection"
    )


@pytest.mark.parametrize(
    "failure", ["403", "404", "timeout", "malformed", "missing_node_id"]
)
def test_failed_recovery_warns_and_retains_rule_and_successful_actors(caplog, failure):
    repository, ctx, rest, _ = _harness([_rule()], [_error()])
    if failure in {"403", "404"}:
        response = requests.Response()
        response.status_code = int(failure)
        rest.get.side_effect = requests.HTTPError(response=response)
    elif failure == "timeout":
        rest.get.side_effect = requests.Timeout("timed out")
    elif failure == "malformed":
        rest.get.return_value.json.return_value = {}
    else:
        payload = rest.get.return_value.json.return_value
        payload["restrictions"]["apps"] = [{"id": 7, "slug": "release"}]

    rows = list(branch_protection_rules.__wrapped__(repository, ctx))

    assert len(rows) == 1
    assert rows[0]["id"] == "RULE_1"
    assert rows[0]["requiresApprovingReviews"] is True
    assert [n["actor"] for n in rows[0]["pushAllowances"]["nodes"]] == [USER, TEAM]
    assert "allowance collection gap" in caplog.text


def test_error_without_allowance_path_is_logged_without_rest_recovery(caplog):
    repository, ctx, rest, graphql = _harness(
        [], [{"type": "FORBIDDEN", "path": ["nodes"]}]
    )
    graphql.post.return_value.json.return_value["data"] = None

    assert list(branch_protection_rules.__wrapped__(repository, ctx)) == []
    rest.get.assert_not_called()
    assert "GraphQL collection gap" in caplog.text
