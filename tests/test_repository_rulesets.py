import duckdb
import json
import logging
from unittest.mock import MagicMock

import requests

from openhound_github.lookup import GithubLookup
from openhound_github.models.repository import Repository
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    repositories_graphql,
)


class _FakeClient:
    def __init__(self, *responses: requests.Response | BaseException) -> None:
        self.responses = list(responses) or [
            _graphql_response(_repository_page_data("R_1", "repo", branch_ruleset_count=2))
        ]
        self.request_paths: list[str] = []
        self.request_variables: list[dict[str, object]] = []

    def post(self, path: str, *, json: dict[str, object]):
        self.request_paths.append(path)
        variables = json["variables"]
        assert isinstance(variables, dict)
        self.request_variables.append({**variables})
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


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


def _graphql_response(
    data: dict[str, object] | None = None,
    *,
    status_code: int = 200,
    text: str | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    if text is not None:
        response._content = text.encode("utf-8")
    else:
        response._content = json.dumps({"data": data or {}}).encode("utf-8")
    response.request = requests.Request("POST", "https://api.github.com/graphql").prepare()
    return response


def _request_pages(client: _FakeClient) -> list[tuple[object, object]]:
    return [
        (variables["after"], variables["count"])
        for variables in client.request_variables
    ]


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


def test_repositories_graphql_uses_dedicated_graphql_client_path() -> None:
    rest_client = _FakeClient()
    graphql_client = _FakeClient()
    ctx = SourceContext(
        client=rest_client,
        organizations=[
            OrgContext(
                client=rest_client,
                graphql_client=graphql_client,
                org_name="org",
            )
        ],
    )

    rows = list(repositories_graphql.__wrapped__(ctx))

    assert [row["id"] for row in rows] == ["R_1"]
    assert graphql_client.request_paths == [""]
    assert rest_client.request_paths == []


def test_repositories_graphql_logs_cursor_and_emitted_count_on_page_failure(
    caplog,
) -> None:
    client = _FakeClient(
        _graphql_response(
            _repository_page_data(
                "R_1",
                "repo",
                branch_ruleset_count=2,
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ),
        ConnectionError("GraphQL page failed after retries"),
    )
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        rows = list(repositories_graphql.__wrapped__(ctx))

    assert len(rows) == 1
    assert (
        "Error in resource 'repositories_graphql' processing organization 'org' "
        "at repository cursor 'cursor-page-2' with page size 100 "
        "after emitting 1 repositories "
        "(ConnectionError): GraphQL page failed after retries"
    ) in caplog.text
    assert _request_pages(client) == [(None, 100), ("cursor-page-2", 100)]


def test_repositories_graphql_emits_all_repository_pages() -> None:
    client = _FakeClient(
        _graphql_response(
            _repository_page_data(
                "R_1",
                "repo-1",
                branch_ruleset_count=2,
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(_repository_page_data("R_2", "repo-2", branch_ruleset_count=0)),
    )
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    rows = list(repositories_graphql.__wrapped__(ctx))

    assert [(row["id"], row["branch_ruleset_count"]) for row in rows] == [
        ("R_1", 2),
        ("R_2", 0),
    ]
    assert _request_pages(client) == [(None, 100), ("cursor-page-2", 100)]


def test_repositories_graphql_retries_gateway_failure_with_smaller_page_size(
    caplog,
) -> None:
    client = _FakeClient(
        _graphql_response(
            _repository_page_data(
                "R_1",
                "repo-1",
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(status_code=502, text="bad gateway"),
        _graphql_response(
            _repository_page_data(
                "R_2",
                "repo-2",
                repository_end_cursor="cursor-page-3",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(_repository_page_data("R_3", "repo-3")),
    )
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    with caplog.at_level(logging.WARNING, logger="openhound_github.resources.organization"):
        rows = list(repositories_graphql.__wrapped__(ctx))

    assert [row["id"] for row in rows] == ["R_1", "R_2", "R_3"]
    assert _request_pages(client) == [
        (None, 100),
        ("cursor-page-2", 100),
        ("cursor-page-2", 50),
        ("cursor-page-3", 100),
    ]
    assert (
        "retrying cursor 'cursor-page-2' with page size 50 after HTTP 502 "
        "at page size 100"
    ) in caplog.text


def test_repositories_graphql_retries_gateway_failure_down_to_25() -> None:
    client = _FakeClient(
        _graphql_response(
            _repository_page_data(
                "R_1",
                "repo-1",
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(status_code=502, text="bad gateway"),
        _graphql_response(status_code=504, text="gateway timeout"),
        _graphql_response(_repository_page_data("R_2", "repo-2")),
    )
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    rows = list(repositories_graphql.__wrapped__(ctx))

    assert [row["id"] for row in rows] == ["R_1", "R_2"]
    assert _request_pages(client) == [
        (None, 100),
        ("cursor-page-2", 100),
        ("cursor-page-2", 50),
        ("cursor-page-2", 25),
    ]


def test_repositories_graphql_logs_terminal_gateway_failure_at_smallest_page_size(
    caplog,
) -> None:
    client = _FakeClient(
        _graphql_response(
            _repository_page_data(
                "R_1",
                "repo-1",
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(status_code=502, text="bad gateway"),
        _graphql_response(status_code=504, text="gateway timeout"),
        _graphql_response(status_code=502, text="bad gateway"),
    )
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        rows = list(repositories_graphql.__wrapped__(ctx))

    assert [row["id"] for row in rows] == ["R_1"]
    assert _request_pages(client) == [
        (None, 100),
        ("cursor-page-2", 100),
        ("cursor-page-2", 50),
        ("cursor-page-2", 25),
    ]
    assert (
        "at repository cursor 'cursor-page-2' with page size 25 "
        "after emitting 1 repositories"
    ) in caplog.text


def test_repositories_graphql_stays_degraded_after_failed_probe() -> None:
    client = _FakeClient(
        _graphql_response(
            _repository_page_data(
                "R_1",
                "repo-1",
                repository_end_cursor="cursor-page-2",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(status_code=502, text="bad gateway"),
        _graphql_response(
            _repository_page_data(
                "R_2",
                "repo-2",
                repository_end_cursor="cursor-page-3",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(status_code=502, text="bad gateway"),
        _graphql_response(
            _repository_page_data(
                "R_3",
                "repo-3",
                repository_end_cursor="cursor-page-4",
                repositories_has_next_page=True,
            )
        ),
        _graphql_response(_repository_page_data("R_4", "repo-4")),
    )
    ctx = SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="org")],
    )

    rows = list(repositories_graphql.__wrapped__(ctx))

    assert [row["id"] for row in rows] == ["R_1", "R_2", "R_3", "R_4"]
    assert _request_pages(client) == [
        (None, 100),
        ("cursor-page-2", 100),
        ("cursor-page-2", 50),
        ("cursor-page-3", 100),
        ("cursor-page-3", 50),
        ("cursor-page-4", 50),
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
