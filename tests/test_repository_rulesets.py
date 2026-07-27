import duckdb
from unittest.mock import MagicMock

from openhound_github.lookup import GithubLookup
from openhound_github.models.repository import Repository
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    repositories_graphql,
)


class _FakeClient:
    def paginate(self, *args, **kwargs):
        return iter(
            [
                [
                    {
                        "organization": {
                            "repositories": {
                                "nodes": [
                                    {
                                        "id": "R_1",
                                        "name": "repo",
                                        "branchRulesets": {"totalCount": 2},
                                        "refs": {
                                            "nodes": [],
                                            "pageInfo": {
                                                "endCursor": None,
                                                "hasNextPage": False,
                                            },
                                        },
                                    }
                                ]
                            }
                        }
                    }
                ]
            ]
        )


def _make_repository() -> Repository:
    return Repository(
        id=1,
        node_id="R_1",
        name="repo",
        full_name="org/repo",
        private=False,
        owner={
            "login": "octocat",
            "id": 1,
            "node_id": "U_1",
            "avatar_url": "",
            "gravatar_id": "",
            "url": "",
            "html_url": "",
            "followers_url": "",
            "following_url": "",
            "gists_url": "",
            "starred_url": "",
            "subscriptions_url": "",
            "organizations_url": "",
            "repos_url": "",
            "events_url": "",
            "received_events_url": "",
            "type": "User",
            "site_admin": False,
        },
        org_login="org",
    )


def test_repositories_graphql_flattens_branch_ruleset_count() -> None:
    client = _FakeClient()
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    rows = list(repositories_graphql.__wrapped__(ctx))

    assert rows == [
        {
            "id": "R_1",
            "name": "repo",
            "refs": {
                "nodes": [],
                "pageInfo": {"endCursor": None, "hasNextPage": False},
            },
            "branch_ruleset_count": 2,
            "org_login": "org",
        }
    ]


def test_repository_node_surfaces_branch_ruleset_presence() -> None:
    repo = _make_repository()
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.repository_branch_ruleset_count.return_value = 2
    repo._lookup = lookup

    node = repo.as_node

    assert node.properties.branch_ruleset_count == 2
    assert node.properties.has_branch_rulesets is True
    lookup.repository_branch_ruleset_count.assert_called_once_with("R_1")


def test_repository_node_preserves_unknown_branch_ruleset_presence() -> None:
    repo = _make_repository()
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.repository_branch_ruleset_count.return_value = None
    repo._lookup = lookup

    node = repo.as_node

    assert node.properties.branch_ruleset_count is None
    assert node.properties.has_branch_rulesets is None


def test_repository_branch_ruleset_count_lookup_returns_int() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.repositories_graphql (id VARCHAR, branch_ruleset_count BIGINT)"
    )
    connection.execute(
        "INSERT INTO github.repositories_graphql VALUES ('R_1', 2), ('R_2', NULL)"
    )

    lookup = GithubLookup(connection)

    assert lookup.repository_branch_ruleset_count("R_1") == 2
    assert lookup.repository_branch_ruleset_count("R_2") is None
