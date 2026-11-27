from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import duckdb
import pytest

from openhound_github.lookup import GithubLookup
from openhound_github.models.app_installation import App, Owner
from openhound_github.models.app_owner import AppOwner
from openhound_github.resources.app_helpers import collect_app_owner
from openhound_github.transforms import ensure_app_installation_input_tables


@pytest.fixture
def lookup():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA github")
        ensure_app_installation_input_tables(con)
        con.execute("CREATE TABLE github.users (id VARCHAR)")
        con.execute("CREATE TABLE github.enterprise_users (id VARCHAR)")
        con.execute("CREATE TABLE github.organizations (node_id VARCHAR)")
        con.execute("CREATE TABLE github.enterprise_organizations (id VARCHAR)")
        con.execute("CREATE TABLE github.enterprise (id VARCHAR)")
        yield GithubLookup(con)


def application(owner_type="User"):
    return App(
        node_id="APP_1",
        slug="example",
        name="Example",
        permissions={},
        events=[],
        owner=Owner(
            id=1,
            node_id="OWNER_1",
            login="owner",
            type=owner_type,
            html_url="https://github.com/owner",
        ),
    )


@pytest.mark.parametrize("owner_type", ["User", "Organization", "Enterprise"])
def test_placeholder_preserves_ownership_without_granting_membership(
    lookup, owner_type
):
    app = application(owner_type)
    owner = AppOwner(**app.owner.model_dump())
    owner._lookup = app._lookup = lookup
    lookup.client.execute(
        "INSERT INTO github.app_owners VALUES (?, ?)", [owner.node_id, owner_type]
    )

    node = owner.as_node
    assert node.id == "OWNER_1"
    assert f"GH_{owner_type}" in node.kinds
    assert node.properties.collected is False
    assert node.properties.environmentid == owner.node_id
    assert node.properties.login == "owner"
    assert owner.edges == []
    assert app.registration_origin == "third_party"
    assert not lookup.app_owner_is_collected(owner.node_id, owner_type)
    assert [(e.start.value, e.end.value) for e in app.edges] == [("OWNER_1", "APP_1")]


@pytest.mark.parametrize(
    "owner_type,table,column",
    [
        ("User", "users", "id"),
        ("User", "enterprise_users", "id"),
        ("Organization", "organizations", "node_id"),
        ("Organization", "enterprise_organizations", "id"),
        ("Enterprise", "enterprise", "id"),
    ],
)
def test_existing_inventory_nodes_are_never_overwritten(
    lookup, owner_type, table, column
):
    lookup.client.execute(f"INSERT INTO github.{table} ({column}) VALUES ('OWNER_1')")
    owner = AppOwner(**application(owner_type).owner.model_dump())
    owner._lookup = lookup
    assert owner.as_node is None


@pytest.mark.parametrize(
    "owner_type,endpoint", [("User", "users"), ("Organization", "orgs")]
)
def test_profiles_are_enriched_once_per_owner(owner_type, endpoint):
    ctx = SimpleNamespace(cache_lock=Lock(), emitted_app_owners=set())
    client = MagicMock()
    client.get.return_value.json.return_value = {
        "node_id": "OWNER_1",
        "type": owner_type,
        "name": "Public name",
        "company": "Example",
        "private_gists": 12,
    }
    app = application(owner_type)
    row = list(collect_app_owner(app, ctx, client))[0]
    assert row["name"] == "Public name"
    assert row["company"] == "Example"
    assert "private_gists" not in row
    assert list(collect_app_owner(app, ctx, client)) == []
    client.get.assert_called_once_with(f"/{endpoint}/owner")


@pytest.mark.parametrize("failure", ["inaccessible", "wrong_id", "wrong_type"])
def test_enrichment_failure_keeps_original_identity(failure):
    ctx = SimpleNamespace(cache_lock=Lock(), emitted_app_owners=set())
    client = MagicMock()
    if failure == "inaccessible":
        client.get.side_effect = RuntimeError("Profile unavailable")
    else:
        client.get.return_value.json.return_value = {
            "node_id": "OTHER" if failure == "wrong_id" else "OWNER_1",
            "type": "Organization" if failure == "wrong_type" else "User",
            "name": "Wrong owner",
        }
    row = list(collect_app_owner(application(), ctx, client))[0]
    assert row["node_id"] == "OWNER_1"
    assert row["name"] is None
    assert row["html_url"] == "https://github.com/owner"


def test_enterprise_identity_needs_no_public_endpoint():
    ctx = SimpleNamespace(cache_lock=Lock(), emitted_app_owners=set())
    client = MagicMock()
    assert len(list(collect_app_owner(application("Enterprise"), ctx, client))) == 1
    client.get.assert_not_called()


def test_unsupported_owner_type_has_no_placeholder(lookup):
    app = application("Bot")
    owner = AppOwner(**app.owner.model_dump())
    owner._lookup = app._lookup = lookup
    ctx = SimpleNamespace(cache_lock=Lock(), emitted_app_owners=set())
    assert owner.as_node is None
    assert app.edges == []
    assert list(collect_app_owner(app, ctx, MagicMock())) == []


@pytest.mark.parametrize("enterprise", [False, True])
def test_owner_resource_collects_and_converts_deduplicated_identities(
    tmp_path, lookup, enterprise
):
    import gzip
    import json

    import dlt
    from dlt.destinations import filesystem
    from openhound.sources.opengraph.entries import GraphContent
    from openhound.sources.opengraph.source import _generate_graph_content

    from openhound_github.resources.enterprise import enterprise_app_owners
    from openhound_github.resources.organization import app_owners
    from openhound_github.source import OrgContext, SourceContext

    client = MagicMock()
    client.get.return_value.json.return_value = {
        "node_id": "OWNER_1",
        "type": "User",
        "name": "Public name",
    }
    ctx = SourceContext(
        client=client, organizations=[OrgContext(org_name="acme", client=client)]
    )

    @dlt.resource(name="applications", columns=App)
    def apps():
        for node_id in ("APP_1", "APP_2"):
            yield application().model_copy(
                update={"node_id": node_id, "environment_slug": "acme"}
            )

    resource = apps()
    transformer = enterprise_app_owners if enterprise else app_owners
    pipeline = dlt.pipeline(
        pipeline_name="owner_test",
        pipelines_dir=str(tmp_path / "pipelines"),
        destination=filesystem(bucket_url=str(tmp_path / "output")),
        dataset_name="github",
    )
    pipeline.run([resource, resource | transformer(ctx)])
    records = []
    for path in (tmp_path / "output" / "github" / "app_owners").glob("*.gz"):
        with gzip.open(path, "rt") as handle:
            records.extend(json.loads(line) for line in handle)
    assert len(records) == 1
    assert records[0]["name"] == "Public name"
    client.get.assert_called_once_with("/users/owner")

    def apply_context(model):
        model._lookup = lookup

    graph = list(_generate_graph_content(records, AppOwner, 150, apply_context))
    assert len(graph) == 1
    GraphContent.model_validate(graph[0])
    node = graph[0]["graph"]["content"]
    assert node["id"] == "OWNER_1"
    assert node["properties"]["collected"] is False
