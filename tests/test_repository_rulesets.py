import duckdb
import logging
from unittest.mock import MagicMock

from openhound_github.lookup import GithubLookup
from openhound_github.models.repository import Repository
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    repositories_graphql,
)


class _FakeClient:
    def __init__(self) -> None:
        self.request_cursors: list[str | None] = []

    def paginate(self, *args, **kwargs):
        self.request_cursors.append(kwargs["json"]["variables"]["after"])
        return iter(
            [
                [
                    _repository_page_data("R_1", "repo", branch_ruleset_count=2)
                ]
            ]
        )


def _repository_page_data(
    repository_id: str,
    repository_name: str,
    *,
    branch_ruleset_count: int | None = None,
    repository_end_cursor: str | None = None,
    repositories_has_next_page: bool = False,
) -> dict:
    return {
        "organization": {
            "repositories": {
                "pageInfo": {
                    "endCursor": repository_end_cursor,
                    "hasNextPage": repositories_has_next_page,
                },
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
    def __init__(self) -> None:
        self.request_cursors: list[str | None] = []

    def paginate(self, *args, **kwargs):
        variables = kwargs["json"]["variables"]
        self.request_cursors.append(variables["after"])
        yield [
            _repository_page_data(
                "R_1",
                "repo",
                branch_ruleset_count=2,
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ]
        variables["after"] = "cursor-page-2"
        self.request_cursors.append(variables["after"])
        raise ConnectionError("GraphQL page failed after retries")


class _TwoPageClient:
    def __init__(self) -> None:
        self.request_cursors: list[str | None] = []

    def paginate(self, *args, **kwargs):
        variables = kwargs["json"]["variables"]
        pages = [
            _repository_page_data(
                "R_1",
                "repo-1",
                branch_ruleset_count=2,
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            ),
            _repository_page_data("R_2", "repo-2", branch_ruleset_count=0),
        ]
        for page in pages:
            self.request_cursors.append(variables["after"])
            yield [page]
            page_info = page["organization"]["repositories"]["pageInfo"]
            if page_info["hasNextPage"]:
                variables["after"] = page_info["endCursor"]


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
    assert client.request_cursors == [None, "cursor-page-2"]


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
    assert client.request_cursors == [None, "cursor-page-2"]


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
