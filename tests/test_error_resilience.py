"""
Tests verifying error-resilient behavior in multi-org resource generators and transformers.

After the fix:
    Each org's processing is isolated in its own try/except block. A failure for
    one org is caught, logged, and iteration continues with the next org — no data
    is silently dropped.
"""
import inspect
import logging
from unittest.mock import MagicMock

from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    applications,
    organizations,
    users,
)


def _success_client(org_name: str) -> MagicMock:
    """Mock RESTClient that returns a minimal org dict for every .get() call."""
    client = MagicMock()
    client.get.return_value.json.return_value = {
        "login": org_name,
        "node_id": f"node_{org_name}",
    }
    return client


def _failing_client(error: Exception) -> MagicMock:
    """Mock RESTClient that raises on any .get() call."""
    client = MagicMock()
    client.get.side_effect = error
    return client


def _graphql_page(org_login: str, logins: list[str]) -> list[dict]:
    """Return one GraphQL page in the shape the `users` resource expects.

    `client.paginate(..., data_selector="data")` yields a list of the items
    extracted from the `data` key.  The `users` resource accesses
    ``page_data[0]["organization"]["membersWithRole"]["edges"]``, so each
    page must be a list whose first element is the parsed GraphQL data dict.
    """
    edges = [{"node": {"id": f"id_{login}", "login": login}, "role": "MEMBER"} for login in logins]
    return [
        {
            "organization": {
                "membersWithRole": {
                    "edges": edges,
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    ]


def test_rest_resource_continues_after_org_failure(caplog) -> None:
    """A mid-iteration REST failure does NOT drop subsequent orgs.

    Setup:
        org1 — succeeds (client.get returns valid org dict)
        org2 — raises ConnectionError on its first API call
        org3 — succeeds

    Expected (fixed behavior):
        org1's data IS yielded.
        org2 is skipped and an error is logged.
        org3's data IS yielded — iteration continues after the failure.
    """
    client1 = _success_client("org1")
    client2 = _failing_client(ConnectionError("HTTP 500: Internal Server Error"))
    client3 = _success_client("org3")

    ctx = SourceContext(
        client=client1,
        organizations=[
            OrgContext(client=client1, org_name="org1"),
            OrgContext(client=client2, org_name="org2"),
            OrgContext(client=client3, org_name="org3"),
        ],
    )

    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        results = list(organizations.bind(ctx))

    yielded_logins = {r.login for r in results}

    assert "org1" in yielded_logins, "org1 data should have been yielded before the error on org2"
    assert "org3" in yielded_logins, "org3 data should still be yielded after org2 fails"

    assert any(
        "Error in resource 'organizations' processing organization 'org2'" in msg
        for msg in caplog.messages
    ), "Expected an error log for org2"


def test_graphql_resource_continues_after_org_failure(caplog) -> None:
    """A mid-iteration GraphQL failure does NOT drop subsequent orgs.

    Setup:
        org1 — paginate succeeds, yields user1
        org2 — paginate raises ConnectionError
        org3 — paginate succeeds, yields user3

    Expected (fixed behavior):
        user1 (org1) IS yielded.
        org2 is skipped and an error is logged.
        user3 (org3) IS yielded.

    Note: the raw generator is called directly (via ``_pipe.gen``) to stay
    within the unit-test boundary and avoid DLT model-validation concerns.
    """
    client1 = MagicMock()
    client1.paginate.return_value = [_graphql_page("org1", ["user1"])]

    client2 = MagicMock()
    client2.paginate.side_effect = ConnectionError("GraphQL endpoint unreachable")

    client3 = MagicMock()
    client3.paginate.return_value = [_graphql_page("org3", ["user3"])]

    ctx = SourceContext(
        client=client1,
        organizations=[
            OrgContext(client=client1, org_name="org1"),
            OrgContext(client=client2, org_name="org2"),
            OrgContext(client=client3, org_name="org3"),
        ],
    )

    # Call the raw generator function to bypass DLT pipeline machinery.
    # parallelized=True wraps the pipe gen with wrap_parallel_iterator (functools.wraps),
    # which yields deferred callables instead of data and loops forever in tests.
    # inspect.unwrap() follows __wrapped__ back to the original generator function.
    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        results = list(inspect.unwrap(users._pipe.gen)(ctx))

    yielded_logins = {r["login"] for r in results}

    assert "user1" in yielded_logins, "user1 (org1) should have been yielded before org2 failed"
    assert "user3" in yielded_logins, "user3 (org3) should still be yielded after org2 fails"

    assert any(
        "Error in resource 'users' processing organization 'org2'" in msg
        for msg in caplog.messages
    ), "Expected an error log for org2"


def test_applications_transformer_handles_api_error(caplog) -> None:
    """A failing API call in the applications transformer is caught and logged.

    The transformer should log the error and yield nothing rather than
    propagating the exception, so that the DLT pipeline can continue with
    the next AppInstallation.

    Note: the raw generator is called directly (via ``_pipe.gen``) because
    DLT transformers use a different calling convention when invoked via
    their decorated interface — the first argument is reserved for upstream
    pipeline items, not direct calls.
    """
    failing_client = MagicMock()
    failing_client.get.side_effect = ConnectionError("HTTP 503: Service Unavailable")

    ctx = SourceContext(
        client=failing_client,
        organizations=[OrgContext(client=failing_client, org_name="org1")],
    )

    # Use a MagicMock to stand in for AppInstallation — the transformer
    # only accesses .id, .app_slug, and .org_login from the install object.
    install = MagicMock()
    install.id = 42
    install.app_slug = "acme-bot"
    install.org_login = "org1"

    # Call the raw generator function to bypass DLT pipeline machinery.
    # Same parallelized=True wrapping issue as users — unwrap to get the original function.
    with caplog.at_level(logging.ERROR, logger="openhound_github.resources.organization"):
        result = list(inspect.unwrap(applications._pipe.gen)(install, ctx))

    assert result == [], "Transformer should yield nothing when the API call fails"

    assert any(
        "Error in resource 'applications' processing app 'acme-bot'" in msg
        for msg in caplog.messages
    ), "Expected an error log for the failing app fetch"
