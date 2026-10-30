import json

import pytest
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from requests import Response
from requests.exceptions import ReadTimeout

from openhound_github.github_rest_client import github_http_session
from openhound_github.helpers import AdaptiveGraphQLPageError, adaptive_graphql_paginate, github_retry_policy


def _page(cursor=None):
    return {"data": {"items": {"pageInfo": {
        "hasNextPage": cursor is not None, "endCursor": cursor,
    }}}}


def _client(monkeypatch, outcomes):
    auth = BearerTokenAuth("test")
    session = github_http_session(github_retry_policy(auth))
    session.send.retry.sleep = lambda _: None
    outcomes = iter(outcomes)
    calls = []

    def send(request, **kwargs):
        calls.append(json.loads(request.body)["variables"] if request.body else {})
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        response = Response()
        response.request = request
        response.url = request.url
        response.status_code = outcome if isinstance(outcome, int) else 200
        payload = outcome if isinstance(outcome, dict) else {"message": "secondary rate limit"}
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(session.get_adapter("https://"), "send", send)
    return RESTClient("https://api.github.com", session=session, auth=auth), calls


def _pages(client):
    return adaptive_graphql_paginate(
        client, query="query", variables={"after": None},
        page_info_path="data.items.pageInfo",
    )


@pytest.mark.parametrize(("outcomes", "sizes"), [
    ([502, 504, 502], [100, 50, 25]),
    ([503, 502, 504], [100, 100, 50]),
    ([503, 503, 502], [100, 100, 100]),
    ([502, ReadTimeout("interrupted"), 503], [100, 50, 50]),
    ([ReadTimeout("interrupted") for _ in range(3)], [100, 100, 100]),
])
def test_adaptive_page_exhausts_three_shared_attempts(monkeypatch, outcomes, sizes):
    client, calls = _client(monkeypatch, [*outcomes, _page()])

    with pytest.raises(AdaptiveGraphQLPageError) as caught:
        list(_pages(client))

    assert [call["count"] for call in calls] == sizes
    assert caught.value.cursor is None
    assert caught.value.page_size == sizes[-1]


def test_smaller_page_recovers_and_next_page_has_fresh_budget(monkeypatch):
    client, calls = _client(monkeypatch, [
        502, 504, _page("next"), 503, 503, _page(),
    ])

    assert len(list(_pages(client))) == 2
    assert [(call["after"], call["count"]) for call in calls] == [
        (None, 100), (None, 50), (None, 25),
        ("next", 100), ("next", 100), ("next", 100),
    ]


def test_later_failure_retains_earlier_page_and_restores_normal_http_retries(monkeypatch):
    client, calls = _client(monkeypatch, [
        _page("next"), 502, 504, 502, 502, 502, _page(),
    ])
    pages = _pages(client)
    assert next(pages) == _page("next")["data"]
    with pytest.raises(AdaptiveGraphQLPageError) as caught:
        next(pages)
    assert caught.value.cursor == "next"
    assert len(calls) == 4

    # A request outside pagination must still retry gateway failures normally.
    assert client.get("/example").status_code == 200
    assert len(calls) == 7


def test_rate_limits_do_not_consume_adaptive_transient_budget(monkeypatch):
    client, calls = _client(monkeypatch, [429, 429, 429, 429, 502, 504, _page()])

    assert len(list(_pages(client))) == 1
    assert [call["count"] for call in calls] == [100] * 5 + [50, 25]
