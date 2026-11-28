import gzip
import json
from unittest.mock import MagicMock

import duckdb
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.personal_access_token import PersonalAccessToken
from openhound_github.models.personal_access_token_request import (
    PersonalAccessTokenRequest,
)
from openhound_github.models.personal_access_token_request_access import (
    PatRequestRepoAccess,
)
from openhound_github.models.scope import scope_node_id
from openhound_github.resources.organization import pat_request_repo_access
from openhound_github.source import OrgContext, SourceContext


SCOPE = scope_node_id("O_1", "repository", "all")


@pytest.fixture
def lookup():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA github")
        con.execute(
            "CREATE TABLE github.organizations (node_id VARCHAR, login VARCHAR, database_id BIGINT)"
        )
        con.execute("INSERT INTO github.organizations VALUES ('O_1', 'Acme', 123)")
        con.execute("CREATE TABLE github.enterprise (id VARCHAR)")
        con.execute("INSERT INTO github.enterprise VALUES ('E_1')")
        con.execute(
            "CREATE TABLE github.enterprise_organizations (id VARCHAR, enterprise_node_id VARCHAR)"
        )
        con.execute("INSERT INTO github.enterprise_organizations VALUES ('O_1', 'E_1')")
        yield GithubLookup(con)


def data(permissions, selection="all"):
    return {
        "id": 10,
        "token_id": 900,
        "token_name": "test",
        "token_expired": False,
        "owner": {
            "login": "alice",
            "id": 1,
            "node_id": "U_1",
            "type": "User",
            "site_admin": False,
        },
        "permissions": permissions,
        "repository_selection": selection,
        "org_login": "acME",
    }


def asset(cls, lookup, permissions, selection="all"):
    if cls is PersonalAccessToken and permissions is None:
        permissions = {"organization": None, "repository": None}
    item = cls.model_validate(data(permissions, selection))
    item._lookup = lookup
    return item


def access_targets(item):
    edges = [edge for edge in item.edges if edge.kind == ek.CAN_ACCESS]
    assert all(not edge.properties.traversable for edge in edges)
    return {edge.end.value for edge in edges}


@pytest.mark.parametrize("selection", ["all", "subset", "none", None])
def test_request_links_requesting_user_to_encoded_request_identity(lookup, selection):
    request = asset(PersonalAccessTokenRequest, lookup, None, selection)
    edges = [e for e in request.edges if e.kind == ek.HAS_PERSONAL_ACCESS_TOKEN_REQUEST]
    assert len(edges) == 1
    assert edges[0].start.value == request.owner.node_id == "U_1"
    assert edges[0].end.value == request.as_node.id
    assert edges[0].end.value.startswith("PATR_")
    assert edges[0].properties.traversable is False


@pytest.mark.parametrize("cls", [PersonalAccessToken, PersonalAccessTokenRequest])
@pytest.mark.parametrize(
    "permissions,organization",
    [
        (None, False),
        ({}, False),
        ({"organization": None}, False),
        ({"organization": {}}, False),
        ({"repository": {"contents": "read"}}, False),
        ({"organization": {"future_permission": "read"}}, False),
        ({"organization": {"members": "read"}}, True),
        ({"repository": {"members": "read"}}, True),
    ],
)
def test_organization_access_requires_nonempty_classified_permissions(
    lookup, cls, permissions, organization
):
    item = asset(cls, lookup, permissions)
    assert access_targets(item) == ({SCOPE, "O_1"} if organization else {SCOPE})
    assert bool(item.as_node.properties.permissions_organization) is organization
    assert any(e.kind == ek.CONTAINS and e.start.value == "O_1" for e in item.edges)


@pytest.mark.parametrize("cls", [PersonalAccessToken, PersonalAccessTokenRequest])
@pytest.mark.parametrize("selection", ["none", None, "selected", "subset"])
def test_only_all_repository_selection_uses_shared_scope(lookup, cls, selection):
    assert access_targets(
        asset(cls, lookup, {"organization": {"members": "read"}}, selection)
    ) == {"O_1"}


@pytest.mark.parametrize("cls", [PersonalAccessToken, PersonalAccessTokenRequest])
def test_enterprise_access_requires_enterprise_permissions_and_matching_parent(
    lookup, cls
):
    item = asset(cls, lookup, {"enterprise": {"enterprise_people": "read"}})
    assert access_targets(item) == {SCOPE, "E_1"}
    assert access_targets(
        asset(cls, lookup, {"organization": {"members": "read"}})
    ) == {SCOPE, "O_1"}


@pytest.mark.parametrize("cls", [PersonalAccessToken, PersonalAccessTokenRequest])
@pytest.mark.parametrize(
    "relationship", ["different_org", "uncollected_parent", "ambiguous"]
)
def test_enterprise_context_is_not_inferred_from_collection_alone(
    lookup, cls, relationship
):
    if relationship == "different_org":
        lookup.client.execute(
            "UPDATE github.enterprise_organizations SET id = 'O_OTHER'"
        )
    elif relationship == "uncollected_parent":
        lookup.client.execute(
            "UPDATE github.enterprise_organizations SET enterprise_node_id = 'E_MISSING'"
        )
    else:
        lookup.client.execute("INSERT INTO github.enterprise VALUES ('E_2')")
        lookup.client.execute(
            "INSERT INTO github.enterprise_organizations VALUES ('O_1', 'E_2')"
        )
    assert access_targets(
        asset(cls, lookup, {"enterprise": {"enterprise_people": "read"}})
    ) == {SCOPE}


@pytest.mark.parametrize("selection", ["subset", "selected"])
def test_selected_request_repository_collection_uses_request_id(lookup, selection):
    request = asset(
        PersonalAccessTokenRequest,
        lookup,
        {"repository": {"contents": "read"}},
        selection,
    )
    client = MagicMock()
    client.paginate.return_value = [[{"node_id": "R_1"}], [{"node_id": "R_2"}]]
    ctx = SourceContext(organizations=[OrgContext(org_name="acME", client=client)])
    records = list(pat_request_repo_access.__wrapped__(request, ctx))
    assert records == [
        {
            "request_id": 10,
            "node_id": "R_1",
            "org_login": "acME",
            "repository_listing_complete": True,
        },
        {
            "request_id": 10,
            "node_id": "R_2",
            "org_login": "acME",
            "repository_listing_complete": True,
        },
    ]
    for record in records:
        record = PatRequestRepoAccess.model_validate(record)
        record._lookup = lookup
        edge = list(record.edges)[0]
        assert edge.start.value == request.node_id
        assert edge.kind == ek.CAN_ACCESS
        assert edge.properties.traversable is False
    client.paginate.assert_called_once_with(
        "/orgs/acME/personal-access-token-requests/10/repositories",
        params={"per_page": 100},
    )


@pytest.mark.parametrize("selection", ["all", "none", None])
def test_request_repository_collection_skips_nonselected_scopes(lookup, selection):
    request = asset(PersonalAccessTokenRequest, lookup, {}, selection)
    client = MagicMock()
    ctx = SourceContext(organizations=[OrgContext(org_name="acME", client=client)])
    assert list(pat_request_repo_access.__wrapped__(request, ctx)) == []
    client.paginate.assert_not_called()


def test_selected_request_pipeline_collects_and_converts_nontraversable_scope(
    tmp_path, lookup
):
    import dlt
    from dlt.destinations import filesystem
    from openhound.sources.opengraph.entries import GraphContent
    from openhound.sources.opengraph.source import _generate_graph_content

    client = MagicMock()
    client.paginate.return_value = [[{"node_id": "R_1"}]]
    ctx = SourceContext(organizations=[OrgContext(org_name="acME", client=client)])

    @dlt.resource(
        name="personal_access_token_requests", columns=PersonalAccessTokenRequest
    )
    def requests():
        yield data({"repository": {"contents": "read"}}, "subset")

    parent = requests()
    pipeline = dlt.pipeline(
        pipeline_name="request_access_test",
        pipelines_dir=str(tmp_path / "pipelines"),
        destination=filesystem(bucket_url=str(tmp_path / "output")),
        dataset_name="github",
    )
    pipeline.run([parent, parent | pat_request_repo_access(ctx)])
    records = []
    for path in (tmp_path / "output/github/pat_request_repo_access").glob("*.gz"):
        with gzip.open(path, "rt") as handle:
            records.extend(json.loads(line) for line in handle)
    assert len(records) == 1

    def context(item):
        item._lookup = lookup

    graph = list(_generate_graph_content(records, PatRequestRepoAccess, 150, context))
    assert len(graph) == 1
    GraphContent.model_validate(graph[0])
    edge = graph[0]["graph"]["content"][0]
    assert edge["kind"] == ek.CAN_ACCESS
    assert edge["start"]["value"].startswith("PATR_")
    assert edge["end"]["value"] == "R_1"
    assert edge["properties"]["traversable"] is False


@pytest.mark.parametrize("partial", [False, True])
def test_request_repository_pagination_failure_is_scoped_and_preserves_incomplete_rows(
    lookup, caplog, partial
):
    request = asset(PersonalAccessTokenRequest, lookup, {}, "selected")

    def pages():
        if partial:
            yield [{"node_id": "R_1"}]
        raise RuntimeError("pagination failed")

    client = MagicMock()
    client.paginate.return_value = pages()
    ctx = SourceContext(organizations=[OrgContext(org_name="acME", client=client)])
    rows = list(pat_request_repo_access.__wrapped__(request, ctx))
    assert rows == (
        [
            {
                "request_id": 10,
                "node_id": "R_1",
                "org_login": "acME",
                "repository_listing_complete": False,
            }
        ]
        if partial
        else []
    )
    log = next(
        r
        for r in caplog.records
        if getattr(r, "resource", None) == "pat_request_repo_access"
    )
    assert log.phase == "resource_iteration"
    assert log.request_id == 10 and log.org_login == "acME"
    assert log.repository_listing_complete is False
    assert "pagination failed" in log.message
    if rows:
        record = PatRequestRepoAccess(**rows[0])
        record._lookup = lookup
        (edge,) = record.edges
        assert edge.properties.repository_listing_complete is False
        assert edge.properties.traversable is False
    # A different request still gets a complete listing.
    request.id = 11
    client.paginate.return_value = [[{"node_id": "R_2"}]]
    subsequent = list(pat_request_repo_access.__wrapped__(request, ctx))
    assert subsequent == [
        {
            "request_id": 11,
            "node_id": "R_2",
            "org_login": "acME",
            "repository_listing_complete": True,
        }
    ]
