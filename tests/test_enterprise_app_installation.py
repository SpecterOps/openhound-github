import gzip
import json
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import dlt
import pytest
import requests
from dlt.destinations import filesystem

from openhound_github.lookup import GithubLookup
from openhound_github.models.app_installation import App, AppInstallation
from openhound_github.models.enterprise import Enterprise
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise_app_installation,
    enterprise_applications,
    enterprise_resources,
)
from openhound_github.resources.organization import (
    applications,
    app_installations,
    app_installation_repo_access,
)


def _payload():
    # Enterprise accounts have a slug/name, and may lack login, type and node_id.
    """Build an enterprise installation response with granted permissions."""
    return {
        "id": 42,
        "app_id": 7,
        "app_slug": "example-app",
        "target_type": "Enterprise",
        "account": {"id": 1, "slug": "acme", "name": "Acme"},
        "repository_selection": "all",
        "permissions": {"enterprise_people": "read"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "suspended_at": "2026-01-03T00:00:00Z",
    }


def _ctx():
    """Build independent app-JWT and enterprise-installation clients."""
    ctx = SourceContext(
        client=MagicMock(), github_app=MagicMock(), enterprise_name="acme"
    )
    ctx.github_app.jwt_headers = {"Authorization": "Bearer test-jwt"}
    ctx.github_app.client.get.return_value.json.return_value = _payload()
    ctx.client.get.return_value.json.return_value = {
        "id": 7,
        "node_id": "APP_7",
        "slug": "example-app",
        "name": "Example",
        "permissions": {"enterprise_people": "read", "contents": "write"},
        "events": [],
        "owner": {"id": 1, "node_id": "E_1", "login": "acme", "type": "enterprise"},
    }
    return ctx


def _collect(ctx):
    """Collect the enterprise installation without authentication discovery."""
    return list(
        enterprise_app_installation.__wrapped__(Enterprise(id="E_1", slug="acme"), ctx)
    )


def test_enterprise_installation_is_collected_independently_with_app_jwt():
    """Fetch installation metadata separately using app JWT authentication."""
    ctx = _ctx()
    installation = AppInstallation(**_collect(ctx)[0])
    ctx.github_app.client.get.assert_called_once_with(
        "/enterprises/acme/installation",
        headers={
            "Authorization": "Bearer test-jwt",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        timeout=30,
    )
    assert installation.account.slug == "acme"
    assert installation.enterprise_node_id == "E_1"
    assert installation.environment_slug == "acme"
    assert installation.org_login is None
    assert installation.as_node.properties.environmentid == "E_1"
    assert installation.as_node.properties.environment_slug == "acme"
    assert installation.as_node.properties.permissions == ["enterprise_people:read"]
    assert installation.as_node.properties.suspended_at is not None
    # No authentication-discovery payload or org client is used.
    ctx.github_app.client.paginate.assert_not_called()
    ctx.client.get.assert_not_called()


def test_enterprise_installation_links_parent_without_repository_access():
    """Link the installation to its enterprise and app without repository grants."""
    installation = AppInstallation(**_collect(_ctx())[0])
    installation._lookup = MagicMock()
    installation._lookup.app_node_id.return_value = "APP_7"
    edges = list(installation.edges)
    assert [(e.kind, e.start.value, e.end.value) for e in edges] == [
        ("GH_Contains", "E_1", "GH_AppInstallation_42"),
        ("GH_InstalledAs", "APP_7", "GH_AppInstallation_42"),
    ]
    assert edges[0].properties.traversable is False
    assert edges[1].properties.traversable is True
    installation._lookup.app_node_id.assert_called_once_with("example-app")


def test_shared_app_has_distinct_enterprise_and_org_installations():
    """Keep distinct installations linked to the same app registration."""
    enterprise_installation = AppInstallation(**_collect(_ctx())[0])
    org_installation = AppInstallation(
        **{
            **_payload(),
            "id": 43,
            "target_type": "Organization",
            "org_login": "org",
        }
    )
    lookup = MagicMock()
    lookup.app_node_id.return_value = "APP_7"
    lookup.org_id_for_login.return_value = "O_1"
    enterprise_installation._lookup = org_installation._lookup = lookup
    enterprise_edges = list(enterprise_installation.edges)
    org_edges = list(org_installation.edges)
    assert enterprise_installation.node_id != org_installation.node_id
    assert enterprise_edges[1].start.value == org_edges[1].start.value == "APP_7"
    assert any(e.kind == "GH_CanAccess" for e in org_edges)
    assert all(e.kind != "GH_CanAccess" for e in enterprise_edges)


def test_enterprise_parent_app_uses_installation_client_and_preserves_requested_permissions():
    """Enrich the parent app with requested permissions using the enterprise token."""
    ctx = _ctx()
    installation = AppInstallation(**_collect(ctx)[0])
    parent = App(**list(enterprise_applications.__wrapped__(installation, ctx))[0])
    parent._lookup = MagicMock()
    parent._lookup.enterprise_id.return_value = "E_1"
    ctx.client.get.assert_called_once_with("/apps/example-app")
    assert set(parent.as_node.properties.permissions) == {
        "contents:write",
        "enterprise_people:read",
    }
    assert parent.as_node.properties.environmentid == "E_1"
    assert parent.edges[0].start.value == "E_1"


@pytest.mark.parametrize("status", [403, 404])
def test_lookup_failure_does_not_break_other_enterprise_collection(status, caplog):
    """Skip inaccessible installations with a diagnostic."""
    ctx = _ctx()
    response = requests.Response()
    response.status_code = status
    ctx.github_app.client.get.side_effect = requests.HTTPError(response=response)
    assert _collect(ctx) == []
    assert "Skipping enterprise app installation" in caplog.text


def test_parent_lookup_failure_preserves_installation(caplog):
    """Retain the installation when parent app enrichment fails."""
    ctx = _ctx()
    installation = AppInstallation(**_collect(ctx)[0])
    ctx.client.get.side_effect = requests.HTTPError("Unavailable")
    assert list(enterprise_applications.__wrapped__(installation, ctx)) == []
    installation._lookup = MagicMock()
    installation._lookup.app_node_id.return_value = None
    assert [e.kind for e in installation.edges] == ["GH_Contains"]
    assert "Skipping app metadata" in caplog.text


def test_pat_collection_has_no_app_installation_requests():
    """Avoid app-JWT requests when collecting with a personal access token."""
    ctx = SourceContext(client=MagicMock(), enterprise_name="acme")
    assert _collect(ctx) == []
    assert "enterprise_app_installation" not in {
        r.name for r in enterprise_resources(ctx)
    }
    ctx.client.get.assert_not_called()


def test_organization_collection_and_enrichment_use_generic_context():
    """Use generic context in organization installation and app resources."""
    client = MagicMock()
    client.paginate.return_value = [[{**_payload(), "target_type": "Organization"}]]
    client.get.return_value.json.return_value = (
        _ctx().client.get.return_value.json.return_value
    )
    ctx = SimpleNamespace(
        organizations=[SimpleNamespace(org_name="org", client=client)],
        cache_lock=Lock(),
        app_cache={},
    )
    row = list(app_installations.__wrapped__(ctx))[0]
    assert row["environment_slug"] == "org"
    assert "org_login" not in row
    installation = AppInstallation(**row)
    enriched = list(applications.__wrapped__(installation, ctx))[0]
    assert enriched["environment_slug"] == "org"
    assert "org_login" not in enriched
    client.get.assert_called_once_with("/apps/example-app")


@pytest.mark.parametrize("selection", ["all", "selected", None])
def test_enterprise_slug_is_never_used_for_organization_operations(selection):
    """Exclude enterprise installations from organization-specific operations."""
    installation = AppInstallation(
        **{
            **_payload(),
            "environment_slug": "acme",
            "enterprise_node_id": "E_1",
            "repository_selection": selection,
        }
    )
    lookup = MagicMock()
    lookup.app_node_id.return_value = "APP_7"
    installation._lookup = lookup
    ctx = _ctx()
    assert list(app_installation_repo_access.__wrapped__(installation, ctx)) == []
    assert list(applications.__wrapped__(installation, ctx)) == []
    assert all(edge.kind != "GH_CanAccess" for edge in installation.edges)
    lookup.org_id_for_login.assert_not_called()
    ctx.client.get.assert_not_called()


def test_legacy_context_fields_are_still_readable():
    """Accept previously collected organization and enterprise context fields."""
    old_org = AppInstallation(
        **{**_payload(), "target_type": "Organization", "org_login": "old-org"}
    )
    old_enterprise = AppInstallation(
        **{
            **_payload(),
            "enterprise_name": "old-enterprise",
            "enterprise_node_id": "E_1",
        }
    )
    old_app = App(
        **{**_ctx().client.get.return_value.json.return_value, "org_login": "old-org"}
    )
    assert old_org.environment_slug == old_app.environment_slug == "old-org"
    assert old_enterprise.environment_slug == "old-enterprise"


def test_environment_slug_takes_precedence_over_legacy_org_login():
    """Prefer canonical context when both legacy and current fields are present."""
    installation = AppInstallation(
        **{
            **_payload(),
            "target_type": "Organization",
            "environment_slug": "new-org",
            "org_login": "old-org",
        }
    )
    installation._lookup = MagicMock()
    installation._lookup.org_id_for_login.return_value = "O_NEW"
    assert installation.as_node.properties.environment_slug == "new-org"
    installation._lookup.org_id_for_login.assert_called_once_with("new-org")


@pytest.mark.parametrize("include_org", [False, True])
@pytest.mark.parametrize("legacy_schema", [False, True])
def test_resources_store_enterprise_and_org_records_in_shared_tables(
    tmp_path, include_org, legacy_schema
):
    """Validate shared tables and migrate legacy nullability constraints."""
    ctx = _ctx()
    # Enterprise installations can omit repository_selection altogether.
    ctx.github_app.client.get.return_value.json.return_value.pop("repository_selection")

    @dlt.resource(name="enterprise", columns=Enterprise)
    def parent():
        """Yield the enterprise that owns the test installation."""
        yield Enterprise(id="E_1", slug="acme")

    @dlt.resource(
        name="org_installations",
        table_name="app_installations",
        columns=AppInstallation,
    )
    def org_installations():
        """Yield an organization installation using canonical context."""
        yield {
            **_payload(),
            "id": 43,
            "target_type": "Organization",
            "environment_slug": "org",
        }

    @dlt.resource(name="org_apps", table_name="applications", columns=App)
    def org_apps():
        """Yield parent app metadata in an organization context."""
        yield {
            **ctx.client.get.return_value.json.return_value,
            "environment_slug": "org",
        }

    @dlt.source
    def source():
        """Combine enterprise and optional organization collection resources."""
        enterprise = parent()
        installation = enterprise | enterprise_app_installation(ctx)
        return [
            enterprise,
            installation,
            installation | enterprise_applications(ctx),
            *([org_installations(), org_apps()] if include_org else []),
        ]

    pipeline = dlt.pipeline(
        pipeline_name="enterprise_app_test",
        destination=filesystem(bucket_url=str(tmp_path / "output")),
        dataset_name="github_test",
        pipelines_dir=str(tmp_path / "pipelines"),
    )
    if legacy_schema:

        class LegacyInstallation(AppInstallation):
            """Represent the earlier organization-only installation schema."""
            org_login: str
            repository_selection: str

        class LegacyApp(App):
            """Represent the earlier organization-only app schema."""
            org_login: str

        @dlt.source(name="source")
        def legacy():
            """Seed the pipeline with the earlier required organization fields."""
            @dlt.resource(name="app_installations", columns=LegacyInstallation)
            def installations():
                """Yield a record conforming to the legacy installation schema."""
                yield {**_payload(), "target_type": "Organization", "org_login": "org"}

            @dlt.resource(name="applications", columns=LegacyApp)
            def apps():
                """Yield a record conforming to the legacy app schema."""
                yield {
                    **ctx.client.get.return_value.json.return_value,
                    "org_login": "org",
                }

            return [installations(), apps()]

        pipeline.run(legacy(), write_disposition="replace", loader_file_format="jsonl")
        assert (
            pipeline.default_schema.tables["app_installations"]["columns"]["org_login"][
                "nullable"
            ]
            is False
        )

    pipeline.run(
        source(),
        write_disposition="replace",
        loader_file_format="jsonl",
        schema_contract={
            "tables": "evolve",
            "columns": "evolve",
            "data_type": "discard_row",
        },
    )
    assert (
        pipeline.default_schema.tables["app_installations"]["columns"]["org_login"][
            "nullable"
        ]
        is True
    )
    assert (
        pipeline.default_schema.tables["app_installations"]["columns"][
            "repository_selection"
        ]["nullable"]
        is True
    )
    assert (
        pipeline.default_schema.tables["applications"]["columns"]["org_login"][
            "nullable"
        ]
        is True
    )

    def stored_rows(table):
        """Read normalized records from the filesystem destination."""
        rows = []
        for path in (tmp_path / "output" / "github_test" / table).glob("*.gz"):
            with gzip.open(path, "rt") as file:
                rows.extend(json.loads(line) for line in file)
        return rows

    installations = [AppInstallation(**row) for row in stored_rows("app_installations")]
    assert {i.id for i in installations} == ({42, 43} if include_org else {42})
    apps = [App(**row) for row in stored_rows("applications")]
    assert len(apps) == (2 if include_org else 1)
    assert {a.node_id for a in apps} == {"APP_7"}

    import duckdb

    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.applications (node_id VARCHAR, slug VARCHAR, org_login VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO github.applications VALUES (?, ?, ?)",
        [(a.node_id, a.slug, a.org_login) for a in apps],
    )
    lookup = GithubLookup(connection)
    for installation in installations:
        installation._lookup = lookup
        assert list(installation._app_edges)[0].start.value == "APP_7"
    connection.close()
