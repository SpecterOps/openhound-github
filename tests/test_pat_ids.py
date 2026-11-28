from base64 import urlsafe_b64decode
from unittest.mock import MagicMock

import duckdb
import msgpack
import pytest

from openhound_github.lookup import GithubLookup
from openhound_github.models.personal_access_token import PersonalAccessToken
from openhound_github.models.personal_access_token_access import PatRepoAccess
from openhound_github.models.personal_access_token_request import (
    PersonalAccessTokenRequest,
)
from openhound_github.pat_ids import pat_node_id, pat_request_node_id
from openhound_github.resources.organization import pat_repo_access
from openhound_github.source import OrgContext, SourceContext


def decode(node_id):
    encoded = node_id.split("_", 1)[1]
    return msgpack.unpackb(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))


@pytest.mark.parametrize(
    "factory,prefix", [(pat_node_id, "PAT"), (pat_request_node_id, "PATR")]
)
def test_ids_encode_version_and_numeric_identity_deterministically(factory, prefix):
    identity = factory(198625609, 11715046)
    assert identity.startswith(prefix + "_")
    assert "=" not in identity
    assert decode(identity) == [1, 198625609, 11715046]
    assert factory(198625609, 11715046) == identity
    assert factory(198625610, 11715046) != identity
    assert factory(198625609, 11715047) != identity
    assert pat_node_id(198625609, 11715046) != pat_request_node_id(198625609, 11715046)


@pytest.mark.parametrize("invalid", [None, 0, -1, True, "123", 2**64])
def test_missing_or_invalid_ids_cannot_generate_colliding_placeholders(invalid):
    with pytest.raises(ValueError, match="organization database ID"):
        pat_node_id(invalid, 1)
    with pytest.raises(ValueError, match="credential database ID"):
        pat_request_node_id(1, invalid)


@pytest.fixture
def lookup():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA inventory")
        con.execute(
            "CREATE TABLE inventory.organizations (node_id VARCHAR, login VARCHAR, database_id BIGINT)"
        )
        con.execute(
            "INSERT INTO inventory.organizations VALUES ('O_1', 'Acme', 123), ('O_2', 'Other', 456)"
        )
        yield GithubLookup(con, "inventory")


def token(lookup):
    asset = PersonalAccessToken(
        id=10,
        token_id=900,
        token_name="ci",
        token_expired=False,
        owner={"login": "alice", "id": 1, "node_id": "U_1", "type": "User"},
        permissions={"repository": {"contents": "write"}},
        org_login="acME",
    )
    asset._lookup = lookup
    return asset


def access(lookup, **overrides):
    asset = PatRepoAccess(
        **{
            "id": 1,
            "node_id": "R_1",
            "full_name": "Acme/repo",
            "private": True,
            "owner": {
                "login": "Acme",
                "id": 123,
                "node_id": "O_1",
                "type": "Organization",
                "site_admin": False,
            },
            "pat_id": 10,
            "org_login": "acme",
            **overrides,
        }
    )
    asset._lookup = lookup
    return asset


def test_pat_uses_grant_id_and_every_reference_uses_the_same_identity(lookup):
    asset = token(lookup)
    assert decode(asset.node_id) == [1, 123, 10]
    assert asset.as_node.id == asset.node_id
    assert asset.as_node.properties.node_id == asset.node_id
    identity = asset.node_id
    asset.token_id = 999
    assert asset.node_id == identity
    assert all(
        edge.start.value == asset.node_id or edge.end.value == asset.node_id
        for edge in asset.edges
    )


@pytest.mark.parametrize("new_record", [False, True])
def test_repository_access_uses_grant_id_without_token_inventory(lookup, new_record):
    record = access(lookup, **({"token_id": 900} if new_record else {}))
    assert record.pat_node_id == token(lookup).node_id
    assert list(record.edges)[0].start.value == token(lookup).node_id
    assert decode(access(lookup, org_login="OTHER").pat_node_id) == [1, 456, 10]


def test_invalid_grant_id_is_rejected(lookup):
    with pytest.raises(ValueError, match="credential database ID"):
        access(lookup, pat_id=0).pat_node_id


def test_missing_organization_id_skips_access_without_encoding_none(lookup, caplog):
    record = access(lookup, org_login="unknown", token_id=900)
    assert record.pat_node_id is None
    assert list(record.edges) == []
    assert "missing or invalid organization database ID" in caplog.text


def test_request_uses_request_id_independently_of_token_id(lookup):
    request = PersonalAccessTokenRequest(
        id=20,
        token_id=900,
        token_name="pending",
        token_expired=False,
        owner={
            "login": "alice",
            "id": 1,
            "node_id": "U_1",
            "type": "User",
            "site_admin": False,
        },
        org_login="ACME",
        repository_selection="all",
    )
    request._lookup = lookup
    assert decode(request.node_id) == [1, 123, 20]
    assert request.node_id != token(lookup).node_id
    assert request.as_node.id == request.node_id
    assert all(
        edge.start.value == request.node_id or edge.end.value == request.node_id
        for edge in request.edges
    )
    identity = request.node_id
    request.token_id = None
    assert request.node_id == identity


def test_collection_keeps_grant_id_for_api_endpoint_and_edges(lookup):
    client = MagicMock()
    client.paginate.return_value = [[{"id": 1, "node_id": "R_1"}]]
    ctx = SourceContext(organizations=[OrgContext(org_name="acME", client=client)])
    rows = list(pat_repo_access.__wrapped__(token(lookup), ctx))
    assert rows == [{"id": 1, "node_id": "R_1", "pat_id": 10, "org_login": "acME"}]
    client.paginate.assert_called_once_with(
        "/orgs/acME/personal-access-tokens/10/repositories", params={"per_page": 100}
    )


@pytest.mark.parametrize("missing", ["absent", "null"])
@pytest.mark.parametrize("kind", ["token", "request", "token_access", "request_access"])
def test_missing_organization_identity_skips_nodes_and_edges_before_encoding(
    lookup, caplog, missing, kind
):
    from openhound_github.models.personal_access_token_request_access import (
        PatRequestRepoAccess,
    )

    if missing == "absent":
        lookup.client.execute(
            "DELETE FROM inventory.organizations WHERE login = 'Acme'"
        )
    else:
        lookup.client.execute(
            "UPDATE inventory.organizations SET database_id = NULL WHERE login = 'Acme'"
        )
    if kind == "token":
        record = token(lookup)
    elif kind == "token_access":
        record = access(lookup)
    elif kind == "request_access":
        record = PatRequestRepoAccess(node_id="R_1", request_id=20, org_login="acme")
        record._lookup = lookup
    else:
        record = PersonalAccessTokenRequest(
            id=20,
            token_name="pending",
            token_expired=False,
            owner={
                "login": "alice",
                "id": 1,
                "node_id": "U_1",
                "type": "User",
                "site_admin": False,
            },
            org_login="acme",
            repository_selection="all",
        )
        record._lookup = lookup
    assert record.as_node is None
    assert list(record.edges) == []
    assert "acme" in caplog.text.lower()
    assert "missing or invalid organization database ID" in caplog.text
    assert any(r.phase == "conversion" for r in caplog.records)
