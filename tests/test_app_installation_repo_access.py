from types import SimpleNamespace
from unittest.mock import MagicMock

import duckdb
from requests import HTTPError, Response

from openhound_github.lookup import GithubLookup
from openhound_github.models.app_installation import AppInstallationRepoAccess
from openhound_github.resources.organization import (
    SourceContext,
    app_installation_repo_access,
)


def _installation(selection="selected"):
    """Build a minimal installation for repository access tests."""
    return SimpleNamespace(
        id=42,
        node_id="GH_AppInstallation_42",
        org_login="example-org",
        repository_selection=selection,
    )


def test_selected_installation_lists_all_pages_with_enterprise_client():
    """Collect every page of repositories granted to a selected installation."""
    client = MagicMock()
    client.paginate.return_value = [
        [{"id": 101, "name": "one", "full_name": "example-org/one"}],
        [{"id": 102, "name": "two", "full_name": "example-org/two"}],
    ]
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    rows = list(app_installation_repo_access.__wrapped__(_installation(), ctx))

    assert rows == [
        {
            "installation_node_id": "GH_AppInstallation_42",
            "repository_database_id": 101,
            "repo_full_name": "example-org/one",
            "org_login": "example-org",
        },
        {
            "installation_node_id": "GH_AppInstallation_42",
            "repository_database_id": 102,
            "repo_full_name": "example-org/two",
            "org_login": "example-org",
        },
    ]
    client.paginate.assert_called_once_with(
        "/enterprises/enterprise/apps/organizations/example-org/"
        "installations/42/repositories",
        params={"per_page": 100},
        headers={"X-GitHub-Api-Version": "2026-03-10"},
    )


def test_all_repositories_do_not_need_extra_request():
    """Skip the repository lookup when an installation already selects all."""
    client = MagicMock()
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    assert list(app_installation_repo_access.__wrapped__(_installation("all"), ctx)) == []
    client.paginate.assert_not_called()


def test_failed_later_page_does_not_emit_partial_access(caplog):
    """Discard earlier pages if a later page fails."""
    client = MagicMock()

    def pages(*args, **kwargs):
        """Yield one page before simulating a pagination failure."""
        yield [{"id": 101, "full_name": "example-org/one"}]
        raise PermissionError("403 Forbidden")

    client.paginate.side_effect = pages
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    assert list(app_installation_repo_access.__wrapped__(_installation(), ctx)) == []
    assert "Skipping repository access" in caplog.text


def test_rate_limit_stops_remaining_selected_installation_requests(caplog):
    """Stop further selected-installation lookups after a rate limit."""
    response = Response()
    response.status_code = 429
    error = HTTPError("429 Too Many Requests", response=response)
    client = MagicMock()
    client.paginate.side_effect = error
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    assert list(app_installation_repo_access.__wrapped__(_installation(), ctx)) == []
    assert list(app_installation_repo_access.__wrapped__(_installation(), ctx)) == []

    client.paginate.assert_called_once()
    assert ctx.selected_installation_repo_access_stopped is True
    assert "skipping remaining installations" in caplog.text


def test_selected_repository_id_resolves_to_access_edge():
    """Resolve repository access within the installation organization."""
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.repositories (node_id VARCHAR, database_id BIGINT, org_login VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.repositories VALUES ('R_1', 101, 'example-org'), ('R_2', 101, 'other-org')"
    )
    access = AppInstallationRepoAccess(
        installation_node_id="GH_AppInstallation_42",
        repository_database_id=101,
        org_login="example-org",
    )
    access._lookup = GithubLookup(connection)

    edges = access.edges

    assert len(edges) == 1
    assert edges[0].start.value == "GH_AppInstallation_42"
    assert edges[0].end.value == "R_1"
    assert edges[0].properties.traversable is False
