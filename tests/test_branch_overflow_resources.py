import json

import pytest
from dlt.sources.helpers.rest_client.client import RESTClient
from requests import Response, Session

from openhound_github.models.repository import RepositoryQL
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    branch_protection_rules,
    branches,
)


@pytest.mark.parametrize("initial_count", [10, 25, 50, 100])
@pytest.mark.parametrize("overflow", [0, 1, 101])
def test_branches_and_protection_rules_follow_initial_page_cursor(monkeypatch, initial_count, overflow):
    total = initial_count + overflow
    def branch(index):
        return {
            "id": f"B_{index}", "name": f"branch-{index}", "target": {"oid": "sha"},
            "branchProtectionRule": {"id": "RULE_initial" if index <= initial_count else "RULE_overflow"},
        }

    repository = RepositoryQL(
        id="R_1", name="repo", org_login="acme",
        refs={
            "nodes": [branch(index) for index in range(1, initial_count + 1)],
            "totalCount": total,
            "pageInfo": {"hasNextPage": total > initial_count, "endCursor": str(initial_count)},
        },
    )
    session = Session()
    calls = []

    def send(request, **kwargs):
        body = json.loads(request.body)
        variables = body["variables"]
        calls.append(variables)
        if "after" in variables:
            start = int(variables["after"])
            end = min(start + variables["count"], total)
            payload = {"repository": {"refs": {
                "nodes": [branch(index) for index in range(start + 1, end + 1)],
                "pageInfo": {"hasNextPage": end < total, "endCursor": str(end)},
            }}}
        else:
            payload = {"nodes": [{"id": rule_id} for rule_id in variables["ids"]]}
        response = Response()
        response.status_code = 200
        response.request = request
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps({"data": payload}).encode()
        return response

    monkeypatch.setattr(session, "send", send)
    client = RESTClient("https://api.github.com", session=session)
    ctx = SourceContext(client=client, organizations=[OrgContext(client=client, org_name="acme")])

    rows = list(branches.__wrapped__(repository, ctx))
    assert [row["id"] for row in rows] == [f"B_{index}" for index in range(1, total + 1)]
    expected_overflow = [] if overflow == 0 else [str(initial_count)] if overflow == 1 else [str(initial_count), str(initial_count + 100)]
    assert [call["after"] for call in calls] == expected_overflow
    assert all(call["count"] == 100 for call in calls)

    calls.clear()
    rules = list(branch_protection_rules.__wrapped__(repository, ctx))
    assert {rule["id"] for rule in rules} == (
        {"RULE_initial"} if overflow == 0 else {"RULE_initial", "RULE_overflow"}
    )
    assert [call["after"] for call in calls if "after" in call] == expected_overflow
    assert repository.refs.total_count == total
