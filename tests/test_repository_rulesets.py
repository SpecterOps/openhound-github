import duckdb
import logging
from types import SimpleNamespace
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
                    _repository_page_data("R_1", "repo", branch_ruleset_count=2)
                ]
            ]
        )


class _Page(list):
    def __init__(self, *args, next_cursor: str | None):
        super().__init__(*args)
        self.request = SimpleNamespace(json={"variables": {"after": next_cursor}})


def _repository_page_data(
    repository_id: str,
    repository_name: str,
    *,
    branch_ruleset_count: int | None = None,
) -> dict:
    return {
        "organization": {
            "repositories": {
                "nodes": [
                    {
                        "id": repository_id,
                        "name": repository_name,
                        "branchRulesets": {"totalCount": branch_ruleset_count},
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


class _FailingSecondPageClient:
    def paginate(self, *args, **kwargs):
        yield _Page(
            [_repository_page_data("R_1", "repo", branch_ruleset_count=2)],
            next_cursor="cursor-page-2",
        )
        raise ConnectionError("GraphQL page failed after retries")


class _TwoPageClient:
    def paginate(self, *args, **kwargs):
        return iter(
            [
                _Page(
                    [_repository_page_data("R_1", "repo-1", branch_ruleset_count=2)],
                    next_cursor="cursor-page-2",
                ),
                _Page(
                    [_repository_page_data("R_2", "repo-2", branch_ruleset_count=0)],
                    next_cursor=None,
                ),
            ]
        )


def _make_repository() -> Repository:
    return Repository(
        id=1,
        node_id="R_1",
        name="repo",
        full_name="org/repo",
        private=False,
        size=0,
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


def test_repositories_graphql_logs_cursor_and_emitted_count_on_page_failure(
    caplog,
) -> None:
    client = _FailingSecondPageClient()
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        rows = list(repositories_graphql.__wrapped__(ctx))

    assert len(rows) == 1
    assert (
        "Error in resource 'repositories_graphql' processing organization 'org' "
        "at repository cursor 'cursor-page-2' after emitting 1 repositories "
        "(ConnectionError): GraphQL page failed after retries"
    ) in caplog.text


def test_repositories_graphql_emits_all_repository_pages() -> None:
    client = _TwoPageClient()
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    rows = list(repositories_graphql.__wrapped__(ctx))

    assert [(row["id"], row["branch_ruleset_count"]) for row in rows] == [
        ("R_1", 2),
        ("R_2", 0),
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
    assert node.properties.size == 0
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
