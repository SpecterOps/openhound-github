import json

import pytest
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from requests import Response
from requests.exceptions import ReadTimeout

from openhound_github.github_rest_client import github_http_session
from openhound_github.helpers import (
    AdaptiveGraphQLPageError,
    adaptive_graphql_paginate,
    github_retry_policy,
)


def _page(cursor=None):
    return {
        "data": {
            "items": {
                "pageInfo": {
                    "hasNextPage": cursor is not None,
                    "endCursor": cursor,
                }
            }
        }
    }


def _client(monkeypatch, outcomes):
    monkeypatch.setattr("openhound_github.helpers.time.sleep", lambda _: None)
    auth = BearerTokenAuth("test")
    session = github_http_session(github_retry_policy(auth))
    session.send.retry.sleep = lambda _: None
    outcomes = iter(outcomes)
    calls = []

    def send(request, **kwargs):
        calls.append(json.loads(request.body)["variables"] if request.body else {})
        outcome = next(outcomes)
        if callable(outcome):
            outcome = outcome(calls[-1])
        if isinstance(outcome, Exception):
            raise outcome
        response = Response()
        response.request = request
        response.url = request.url
        response.status_code = outcome if isinstance(outcome, int) else 200
        payload = (
            outcome
            if isinstance(outcome, dict)
            else {"message": "secondary rate limit"}
        )
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(session.get_adapter("https://"), "send", send)
    return RESTClient("https://api.github.com", session=session, auth=auth), calls


def _pages(client):
    return adaptive_graphql_paginate(
        client,
        query="query",
        variables={"after": None},
        page_info_path="data.items.pageInfo",
    )


@pytest.mark.parametrize(
    ("outcomes", "sizes"),
    [
        ([502, 504, 502, 504, 502], [100, 50, 25, 25, 25]),
        ([503, 502, 504], [100, 100, 50]),
        ([503, 503, 502], [100, 100, 100]),
        ([502, ReadTimeout("interrupted"), 503], [100, 50, 50]),
        ([ReadTimeout("interrupted") for _ in range(3)], [100, 100, 100]),
    ],
)
def test_adaptive_page_bounds_shared_and_reserved_attempts(
    monkeypatch, outcomes, sizes
):
    client, calls = _client(monkeypatch, [*outcomes, _page()])

    with pytest.raises(AdaptiveGraphQLPageError) as caught:
        list(_pages(client))

    assert [call["count"] for call in calls] == sizes
    assert caught.value.cursor is None
    assert caught.value.page_size == sizes[-1]


def test_smaller_page_recovers_and_next_page_has_fresh_budget(monkeypatch):
    client, calls = _client(
        monkeypatch,
        [
            502,
            504,
            _page("next"),
            503,
            503,
            _page(),
        ],
    )

    assert len(list(_pages(client))) == 2
    assert [(call["after"], call["count"]) for call in calls] == [
        (None, 100),
        (None, 50),
        (None, 25),
        ("next", 100),
        ("next", 100),
        ("next", 100),
    ]


def test_later_failure_retains_earlier_page_and_restores_normal_http_retries(
    monkeypatch,
):
    client, calls = _client(
        monkeypatch,
        [
            _page("next"),
            502,
            504,
            502,
            502,
            502,
            502,
            502,
            _page(),
        ],
    )
    pages = _pages(client)
    assert next(pages) == _page("next")["data"]
    with pytest.raises(AdaptiveGraphQLPageError) as caught:
        next(pages)
    assert caught.value.cursor == "next"
    assert len(calls) == 6

    # A request outside pagination must still retry gateway failures normally.
    assert client.get("/example").status_code == 200
    assert len(calls) == 9


@pytest.mark.parametrize("gateway", [502, 504])
def test_smallest_page_retries_with_jitter_and_retains_cursor(monkeypatch, gateway):
    client, calls = _client(monkeypatch, [gateway] * 4 + [_page()])
    delays = []
    bounds = []

    def uniform(low, high):
        bounds.append((low, high))
        return (low + high) / 2

    monkeypatch.setattr("openhound_github.helpers.random.uniform", uniform)
    monkeypatch.setattr("openhound_github.helpers.time.sleep", delays.append)

    pages = adaptive_graphql_paginate(
        client,
        query="query",
        variables={"after": "saved-cursor"},
        page_info_path="data.items.pageInfo",
    )
    assert len(list(pages)) == 1
    assert [call["count"] for call in calls] == [100, 50, 25, 25, 25]
    assert all(call["after"] == "saved-cursor" for call in calls)
    assert bounds == [(1, 2)]
    assert delays == [1.5, 15]


def test_reserved_attempt_does_not_add_nested_http_retries(monkeypatch):
    client, calls = _client(monkeypatch, [502, 504, 502, 503, _page()])

    with pytest.raises(AdaptiveGraphQLPageError):
        list(_pages(client))

    assert [call["count"] for call in calls] == [100, 50, 25, 25]


def test_rate_limits_do_not_consume_adaptive_transient_budget(monkeypatch):
    client, calls = _client(monkeypatch, [429, 429, 429, 429, 502, 504, _page()])

    assert len(list(_pages(client))) == 1
    assert [call["count"] for call in calls] == [100] * 5 + [50, 25]


def test_explicit_repository_batches_isolate_gateway_failure_and_continue(
    monkeypatch, caplog
):
    from itertools import repeat
    from openhound_github.helpers import graphql_repository_batches

    ids = [f"R_{index}" for index in range(201)]

    def outcome(variables):
        batch = variables["ids"]
        if "R_125" in batch:
            return 502
        return {"data": {"nodes": [{"id": node_id} for node_id in batch]}}

    client, calls = _client(monkeypatch, repeat(outcome))
    delays = []
    monkeypatch.setattr("openhound_github.helpers.time.sleep", delays.append)
    rows = list(
        graphql_repository_batches(
            client,
            query="query",
            repository_ids=ids,
            org_name="org",
            repository_names={"R_125": "org/broken"},
        )
    )
    assert [row["id"] for row in rows] == [
        node_id for node_id in ids if node_id != "R_125"
    ]
    assert [len(call["ids"]) for call in calls[:5]] == [50, 50, 50, 25, 25]
    assert calls[-1]["ids"] == ["R_200"]
    assert len(delays) == 2
    assert 1 <= delays[0] <= 2
    assert delays[1] == 15
    assert "org/broken" in caplog.text
    assert "collection gap" in caplog.text


def test_explicit_repository_batches_bound_work_during_outage(monkeypatch):
    from itertools import repeat
    from openhound_github.helpers import graphql_repository_batches

    client, calls = _client(monkeypatch, repeat(504))
    rows = list(
        graphql_repository_batches(
            client,
            query="query",
            repository_ids=[str(i) for i in range(100)],
            org_name="org",
        )
    )
    assert rows == []
    # Two binary split trees have 198 requests plus two retries per 25-ID group.
    assert len(calls) == 206


def test_explicit_repository_batches_retain_partial_data_and_retry_only_gaps(
    monkeypatch,
):
    from openhound_github.helpers import graphql_repository_batches

    client, calls = _client(
        monkeypatch,
        [
            {
                "data": {"nodes": [{"id": "good"}, {"id": "partial"}, None]},
                "errors": [{"path": ["nodes", 1, "refs"], "message": "timeout"}],
            },
            {"data": {"nodes": [{"id": "partial"}]}},
            {"data": {"nodes": [None]}},
        ],
    )
    rows = list(
        graphql_repository_batches(
            client,
            query="query",
            repository_ids=["good", "partial", "missing", "good"],
            org_name="org",
        )
    )
    assert [row["id"] for row in rows] == ["good", "partial"]
    assert [call["ids"] for call in calls] == [
        ["good", "partial", "missing"],
        ["partial"],
        ["missing"],
    ]


def test_explicit_repository_batches_continue_after_http_failure(monkeypatch):
    from openhound_github.helpers import graphql_repository_batches

    client, calls = _client(monkeypatch, [404, {"data": {"nodes": [{"id": "50"}]}}])
    rows = list(
        graphql_repository_batches(
            client,
            query="query",
            repository_ids=[str(i) for i in range(51)],
            org_name="org",
        )
    )
    assert rows == [{"id": "50"}]
    assert len(calls) == 2


@pytest.mark.parametrize("branch_count", [10, 25, 50, 100])
@pytest.mark.parametrize("batch_size", [1, 25, 50, 100])
def test_explicit_repository_batch_size_is_configurable(monkeypatch, batch_size, branch_count):
    from itertools import repeat
    from openhound_github.helpers import graphql_repository_batches

    def outcome(variables):
        return {"data": {"nodes": [{"id": node_id} for node_id in variables["ids"]]}}

    client, calls = _client(monkeypatch, repeat(outcome))
    ids = [str(i) for i in range(101)]
    rows = list(graphql_repository_batches(
        client, query="query", repository_ids=ids, org_name="org", batch_size=batch_size, initial_branch_count=branch_count,
    ))
    assert [row["id"] for row in rows] == ids
    assert all(call["branch_count"] == branch_count for call in calls)
    assert [call["ids"] for call in calls] == [ids[i:i + batch_size] for i in range(0, 101, batch_size)]


@pytest.mark.parametrize("batch_size", [0, -1, 101, True, 1.5, "50"])
def test_explicit_repository_batch_size_rejects_invalid_values(batch_size):
    from openhound_github.helpers import graphql_repository_batches

    with pytest.raises(ValueError, match="integer between 1 and 100"):
        list(graphql_repository_batches(None, query="query", repository_ids=[], org_name="org", batch_size=batch_size))


@pytest.mark.parametrize("branch_count", [0, -1, 101, True, 1.5, "10"])
def test_initial_branch_count_rejects_invalid_values(branch_count):
    from openhound_github.helpers import graphql_repository_batches

    with pytest.raises(ValueError, match="initial_branch_count must be an integer between 1 and 100"):
        list(graphql_repository_batches(None, query="query", repository_ids=[], org_name="org", initial_branch_count=branch_count))


def test_batch_diagnostics_report_retries_and_request_time(monkeypatch, caplog):
    import logging
    from openhound_github.helpers import graphql_repository_batches

    client, calls = _client(monkeypatch, [502, 504, {"data": {"nodes": [{"id": "R_1", "body": "private-response"}]}}])
    ticks = iter([0, 1, 2, 4, 5, 8])
    from types import SimpleNamespace
    monkeypatch.setattr("openhound_github.helpers.time", SimpleNamespace(monotonic=lambda: next(ticks), sleep=lambda _: None, time=__import__("time").time))
    with caplog.at_level(logging.DEBUG, logger="openhound_github.helpers"):
        rows = list(graphql_repository_batches(
            client, query="private-query", repository_ids=["R_1"], org_name="org",
            repository_names={"R_1": "org/repo"}, initial_branch_count=10,
        ))
    assert len(rows) == 1
    records = [record for record in caplog.records if record.name == "openhound_github.helpers"]
    started = [record for record in records if "request started:" in record.message]
    finished = [record for record in records if "request finished:" in record.message]
    assert len(started) == len(finished) == len(calls) == 3
    assert started[0].repository_ids == ["R_1"]
    assert started[0].initial_branch_count == 10
    assert "org/repo" in started[0].message
    assert [record.http_status for record in finished] == [502, 504, 200]
    assert [record.duration_seconds for record in finished] == [1, 2, 3]
    summary = next(record for record in records if "collection summary" in record.message)
    assert summary.initial_batches == 1
    assert summary.successful_initial_batches == 0
    assert summary.recovered_initial_batches == 1
    assert summary.incomplete_initial_batches == 0
    assert summary.batch_attempts == 3
    assert summary.failed_batch_attempts == 2
    assert summary.unresolved_repositories == 0
    assert summary.request_seconds == 6
    assert "private-response" not in caplog.text
    assert "private-query" not in caplog.text
    assert "Bearer" not in caplog.text


def test_batch_diagnostics_distinguish_recovered_and_incomplete_batches(monkeypatch, caplog):
    import logging
    from itertools import repeat
    from openhound_github.helpers import graphql_repository_batches

    def outcome(variables):
        ids = variables["ids"]
        if len(ids) == 50 and ids[0] == "0":
            return 502
        if ids == ["100"]:
            return 404
        return {"data": {"nodes": [{"id": node_id} for node_id in ids]}}

    client, _ = _client(monkeypatch, repeat(outcome))
    with caplog.at_level(logging.INFO, logger="openhound_github.helpers"):
        rows = list(graphql_repository_batches(client, query="query", repository_ids=[str(i) for i in range(101)], org_name="org"))
    assert len(rows) == 100
    summary = next(record for record in caplog.records if "collection summary" in record.message)
    assert summary.requested_repositories == 101
    assert summary.emitted_repositories == 100
    assert summary.initial_batches == 3
    assert summary.successful_initial_batches == 1
    assert summary.recovered_initial_batches == 1
    assert summary.incomplete_initial_batches == 1
    assert summary.unresolved_repositories == 1
    assert summary.splits == 1
    assert summary.batch_attempts == 5
    assert summary.failed_batch_attempts == 2
    assert "request started:" not in caplog.text


def test_batch_diagnostics_report_empty_inventory(caplog):
    import logging
    from openhound_github.helpers import graphql_repository_batches

    with caplog.at_level(logging.INFO, logger="openhound_github.helpers"):
        assert list(graphql_repository_batches(None, query="query", repository_ids=[], org_name="empty")) == []
    summary = next(record for record in caplog.records if "collection summary" in record.message)
    assert summary.initial_batches == summary.batch_attempts == summary.emitted_repositories == 0
    assert summary.request_seconds == 0


@pytest.mark.parametrize("direct_session", [False, True])
@pytest.mark.parametrize(("status", "expected_attempts"), [(200, 1), (404, 1), (503, 3)])
def test_session_avoids_dlt_warning_and_preserves_http_errors(
    monkeypatch, caplog, direct_session, status, expected_attempts
):
    client, calls = _client(monkeypatch, [status] * expected_attempts)
    assert not client.session.raise_for_status
    assert "The session provided has raise_for_status enabled" not in caplog.text
    target = client.session if direct_session else client
    if status == 200:
        assert target.get("https://api.github.com/example").status_code == 200
    else:
        from requests.exceptions import HTTPError
        with pytest.raises(HTTPError) as caught:
            target.get("https://api.github.com/example")
        assert caught.value.response.status_code == status
    assert len(calls) == expected_attempts
