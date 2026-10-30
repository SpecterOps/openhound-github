"""Exercise exhausted retries through the real parallel DLT resource wrappers."""

import json
import logging
from collections import Counter
from threading import Lock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import dlt
import pytest
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator
from requests import Response
from requests.exceptions import ReadTimeout

from openhound_github.github_rest_client import github_http_session
from openhound_github.helpers import github_retry_policy
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    environment_branch_policies,
    environment_secrets,
    environment_variables,
    environments,
    organizations,
)


def _client(monkeypatch, route):
    session = github_http_session(github_retry_policy(BearerTokenAuth("test")))
    session.send.retry.sleep = lambda _: None
    calls = Counter()
    lock = Lock()

    def send(request, **kwargs):
        url = urlparse(request.url)
        page = parse_qs(url.query).get("page", ["1"])[0]
        with lock:
            calls[url.path, page] += 1
        outcome = route(url.path, page)
        if isinstance(outcome, Exception):
            raise outcome
        status, payload, more = outcome
        response = Response()
        response.status_code = status
        response.url = request.url
        response.request = request
        response._content = json.dumps(payload).encode()
        if more:
            response.headers["Link"] = f'<https://api.github.com{url.path}?page=2>; rel="next"'
        return response

    monkeypatch.setattr(session.get_adapter("https://"), "send", send)
    return RESTClient(
        "https://api.github.com", session=session, paginator=HeaderLinkPaginator(),
    ), calls


def _failure(error):
    return ReadTimeout("simulated read timeout") if error == "timeout" else (
        503, {"message": "simulated unavailable endpoint"}, False,
    )


def _field(row, name):
    return row[name] if isinstance(row, dict) else getattr(row, name)


@pytest.mark.parametrize("error", ["503", "timeout"])
def test_later_organizations_collect_after_exhausted_retries(monkeypatch, caplog, error):
    def route(path, page):
        if path == "/orgs/bad":
            return _failure(error)
        org = path.split("/")[2]
        return 200, {"login": org, "node_id": f"ORG_{org}"}, False

    client, calls = _client(monkeypatch, route)
    ctx = SourceContext(client=client, organizations=[
        OrgContext(client=client, org_name=name) for name in ("first", "bad", "last")
    ])

    with caplog.at_level(logging.ERROR):
        rows = list(organizations(ctx))

    assert {_field(row, "login") for row in rows} == {"first", "last"}
    assert calls["/orgs/bad", "1"] == 3
    assert "processing organization 'bad'" in caplog.text


@pytest.mark.parametrize("error", ["503", "timeout"])
def test_later_repositories_collect_and_partial_page_is_retained(monkeypatch, caplog, error):
    def route(path, page):
        repo = path.split("/")[3]
        if repo == "bad" and page == "2":
            return _failure(error)
        environment = {
            "id": 1, "node_id": f"ENV_{repo}", "name": repo,
            "url": "https://api.github.com/example", "html_url": "https://github.com/example",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }
        return 200, {"environments": [environment]}, repo == "bad"

    client, calls = _client(monkeypatch, route)
    ctx = SourceContext(client=client, organizations=[OrgContext(client=client, org_name="org")])
    parents = dlt.resource([
        SimpleNamespace(id=f"REPO_{name}", name=name, org_login="org", environment_count=1)
        for name in ("first", "bad", "last")
    ], name="probe_repositories")

    with caplog.at_level(logging.ERROR):
        rows = list(parents | environments(ctx))

    assert {_field(row, "repository_name") for row in rows} == {"first", "bad", "last"}
    assert calls["/repos/org/bad/environments", "2"] == 3
    assert "resource 'environments'" in caplog.text
    assert "/repos/org/bad/environments" in caplog.text or error == "timeout"


@pytest.mark.parametrize("transformer, suffix, selector", [
    (environment_variables, "variables", "variables"),
    (environment_secrets, "secrets", "secrets"),
    (environment_branch_policies, "deployment-branch-policies", "branch_policies"),
])
@pytest.mark.parametrize("error", ["503", "timeout"])
def test_later_environments_collect_after_partial_failure(
    monkeypatch, caplog, transformer, suffix, selector, error,
):
    def route(path, page):
        name = path.split("/")[5]
        if name == "bad" and page == "2":
            return _failure(error)
        item = {"name": "item", "value": "value", "id": 1, "node_id": "POLICY",
                "created_at": "2026-01-01T00:00:00Z"}
        return 200, {selector: [item]}, name == "bad"

    client, calls = _client(monkeypatch, route)
    ctx = SourceContext(client=client, organizations=[OrgContext(client=client, org_name="org")])
    parents = dlt.resource([
        SimpleNamespace(
            name=name, node_id=f"ENV_{name}", org_login="org", repository_name="repo",
            repository_full_name="org/repo", repository_node_id="REPO",
            has_custom_branch_policies=True, required_reviewers=False, prevent_self_review=False,
        ) for name in ("first", "bad", "last")
    ], name="probe_environments")

    with caplog.at_level(logging.ERROR):
        rows = list(parents | transformer(ctx))

    assert {_field(row, "environment_name") for row in rows} == {"first", "bad", "last"}
    assert calls[f"/repos/org/repo/environments/bad/{suffix}", "2"] == 3
    assert f"resource '{transformer.name}'" in caplog.text
