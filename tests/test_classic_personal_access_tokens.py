import gzip
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import dlt
import pytest
import requests
import duckdb
from dlt.destinations import filesystem

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.classic_personal_access_token import (
    ClassicPersonalAccessToken,
)
from openhound_github.models.enterprise_member import BaseUser
from openhound_github.models.enterprise import Enterprise
from openhound_github.resources.enterprise import (
    SourceContext,
    _download_enterprise_credential_inventory,
    classic_personal_access_tokens,
    enterprise_credential_inventory,
)


class Response:
    def __init__(self, status_code, *, payload=None, content=b"", headers=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.content = content
        self.raw = io.BytesIO(content)
        self.headers = headers or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error_response = requests.Response()
            error_response.status_code = self.status_code
            raise requests.HTTPError(response=error_response)

    def close(self):
        self.raw.close()

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]


def test_classic_pat_export_polls_one_job_and_deduplicates_org_rows(monkeypatch):
    client = MagicMock()
    client.post.return_value = Response(
        202, payload={"export_id": "export-1", "as_of": "2026-10-05T20:00:00Z"}
    )
    client.get.side_effect = [
        Response(200, payload={"status": "started"}),
        Response(302, headers={"Location": "https://example.test/signed.csv"}),
    ]
    csv_content = (
        "credential_type,credential_id,hashed_token,display_name,owner_id,owner,scopes,"
        "credential_state,expiry_status,enterprise_authorized,authorization_count,organization,created_at\n"
        'classic_pat,42,hash-42,"CI, deploy",7,octocat,"repo; read:org",active,expires,true,3,acme,2026-01-01T00:00:00Z\n'
        'classic_pat,42,hash-42,"CI, deploy",7,octocat,"repo; read:org",active,expires,true,3,ops,2026-01-01T00:00:00Z\n'
        "classic_pat,43,hash-43,Personal,8,hubot,repo,expired,expires,false,0,,2026-01-01T00:00:00Z\n"
        "fine_grained_pat,42,hash-fg,Other,8,hubot,,active,never,false,1,acme,2026-01-01T00:00:00Z\n"
    )
    download = MagicMock(return_value=Response(200, content=csv_content.encode()))
    monkeypatch.setattr("openhound_github.resources.enterprise.requests.get", download)
    monkeypatch.setattr(
        "openhound_github.resources.enterprise.time.sleep", lambda _: None
    )

    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )
    inventories = list(
        enterprise_credential_inventory.__wrapped__(SimpleNamespace(id="E_1"), ctx)
    )
    assert len(inventories) == 1
    inventory = inventories[0]
    assert inventory["export_id"] == "export-1"
    assert inventory["as_of"] == "2026-10-05T20:00:00Z"
    assert len(inventory["rows"]) == 4
    assert inventory["rows"][3]["credential_type"] == "fine_grained_pat"
    assert inventory["rows"][3]["hashed_token"] == "hash-fg"
    assert "hashed_token" in inventory["columns"]
    rows = list(classic_personal_access_tokens.__wrapped__(inventory))

    assert len(rows) == 2
    assert rows[0]["credential_id"] == 42
    assert rows[0]["display_name"] == "CI, deploy"
    assert rows[0]["scopes"] == ["repo", "read:org"]
    assert rows[0]["enterprise_authorized"] is True
    assert rows[0]["authorization_count"] == 3
    assert rows[0]["inventory_as_of"] == "2026-10-05T20:00:00Z"
    assert rows[0]["authorized_organizations"] == ["acme", "ops"]
    assert rows[1]["authorized_organizations"] == []
    assert rows[1]["enterprise_authorized"] is False
    assert rows[1]["credential_state"] == "expired"
    client.post.assert_called_once_with(
        "/enterprises/enterprise/credentials/exports",
        headers={"X-GitHub-Api-Version": "2026-03-10"},
    )
    assert client.get.call_count == 2
    assert client.get.call_args.kwargs["allow_redirects"] is False
    download.assert_called_once_with(
        "https://example.test/signed.csv", timeout=120, stream=True
    )


def test_one_export_persists_raw_rows_and_models_only_classic_pats(
    monkeypatch, tmp_path
):
    calls = []

    def inventory_rows(client, slug):
        calls.append(slug)
        return {
            "export_id": "export-1",
            "as_of": "2026-10-05T20:00:00Z",
            "columns": ["credential_type", "credential_id", "hashed_token"],
            "rows": [
                {
                    "credential_type": "classic_pat",
                    "credential_id": "42",
                    "hashed_token": "hash-classic",
                },
                {
                    "credential_type": "oauth_app_user_token",
                    "credential_id": "42",
                    "hashed_token": "hash-oauth",
                },
            ],
        }

    monkeypatch.setattr(
        "openhound_github.resources.enterprise._download_enterprise_credential_inventory",
        inventory_rows,
    )

    @dlt.resource(name="probe_enterprise", columns=Enterprise)
    def parent():
        yield Enterprise(id="E_1", slug="enterprise")

    @dlt.source
    def source():
        enterprise = parent()
        inventory = enterprise | enterprise_credential_inventory(
            SourceContext(
                client=object(), enterprise_name="enterprise", deployment_type="ghec"
            )
        )
        return [enterprise, inventory, inventory | classic_personal_access_tokens()]

    pipeline = dlt.pipeline(
        pipeline_name="credential_inventory_test",
        destination=filesystem(bucket_url=str(tmp_path / "output")),
        dataset_name="github_test",
        pipelines_dir=str(tmp_path / "pipelines"),
    )
    pipeline.run(source())

    def stored_rows(table):
        rows = []
        for path in (tmp_path / "output" / "github_test" / table).glob("*.gz"):
            with gzip.open(path, "rt") as file:
                rows.extend(json.loads(line) for line in file)
        return rows

    raw = stored_rows("enterprise_credential_inventory")
    modeled = stored_rows("classic_personal_access_tokens")
    assert calls == ["enterprise"]
    assert len(raw) == 1
    assert raw[0]["rows"][1]["credential_type"] == "oauth_app_user_token"
    assert raw[0]["rows"][1]["hashed_token"] == "hash-oauth"
    assert len(modeled) == 1
    assert modeled[0]["credential_id"] == 42

    fallback_calls = []

    def retry_inventory(client, slug, export_id=None):
        fallback_calls.append((slug, export_id))
        if export_id is None:
            Response(429).raise_for_status()
        return inventory_rows(client, slug)

    monkeypatch.setattr(
        "openhound_github.resources.enterprise._download_enterprise_credential_inventory",
        retry_inventory,
    )
    pipeline.run(source())
    assert fallback_calls == [("enterprise", None), ("enterprise", "export-1")]


def test_classic_pat_inventory_rate_limit_skips_without_starting_another_export(caplog):
    client = MagicMock()
    client.post.return_value = Response(429)
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    assert (
        list(
            enterprise_credential_inventory.__wrapped__(SimpleNamespace(id="E_1"), ctx)
        )
        == []
    )
    assert client.post.call_count == 1
    assert "daily export limit reached" in caplog.text


def test_classic_pat_inventory_reuses_recent_export_on_rate_limit(monkeypatch, caplog):
    state = {
        "last_export_id": "prior-1",
        "last_export_enterprise": "enterprise",
        "last_export_as_of": "2026-10-05T20:00:00Z",
        "last_export_downloaded_at": 1000,
    }
    monkeypatch.setattr(
        "openhound_github.resources.enterprise.dlt.current.resource_state",
        lambda _: state,
    )
    monkeypatch.setattr("openhound_github.resources.enterprise.time.time", lambda: 1001)
    client = MagicMock()
    client.post.return_value = Response(429)
    client.get.return_value = Response(
        302, headers={"Location": "https://example.test/prior.csv"}
    )
    monkeypatch.setattr(
        "openhound_github.resources.enterprise.requests.get",
        lambda *_, **__: Response(
            200, content=b"credential_type,credential_id\nclassic_pat,42\n"
        ),
    )
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    inventories = list(
        enterprise_credential_inventory.__wrapped__(SimpleNamespace(id="E_1"), ctx)
    )
    assert len(inventories) == 1
    assert inventories[0]["export_id"] == "prior-1"
    assert inventories[0]["as_of"] == "2026-10-05T20:00:00Z"
    assert "using prior export" in caplog.text
    client.get.assert_called_once()


def test_classic_pat_inventory_does_not_reuse_stale_export(monkeypatch):
    monkeypatch.setattr(
        "openhound_github.resources.enterprise.dlt.current.resource_state",
        lambda _: {
            "last_export_id": "prior-1",
            "last_export_enterprise": "enterprise",
            "last_export_downloaded_at": 1000,
        },
    )
    monkeypatch.setattr(
        "openhound_github.resources.enterprise.time.time", lambda: 1000 + 86401
    )
    client = MagicMock()
    client.post.return_value = Response(429)
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    assert (
        list(
            enterprise_credential_inventory.__wrapped__(SimpleNamespace(id="E_1"), ctx)
        )
        == []
    )
    client.get.assert_not_called()


def test_classic_pat_collection_skips_ghes():
    client = MagicMock()
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghes"
    )

    assert (
        list(
            enterprise_credential_inventory.__wrapped__(SimpleNamespace(id="E_1"), ctx)
        )
        == []
    )
    client.post.assert_not_called()


def test_classic_pat_export_rejects_non_https_download(monkeypatch):
    client = MagicMock()
    client.post.return_value = Response(202, payload={"export_id": "export-1"})
    client.get.return_value = Response(
        302, headers={"Location": "http://example.test/file.csv"}
    )
    download = MagicMock()
    monkeypatch.setattr("openhound_github.resources.enterprise.requests.get", download)

    with pytest.raises(ValueError, match="invalid HTTPS download URL"):
        _download_enterprise_credential_inventory(client, "enterprise")
    download.assert_not_called()


def test_classic_pat_failed_export_produces_no_partial_inventory(caplog):
    client = MagicMock()
    client.post.return_value = Response(202, payload={"export_id": "export-1"})
    client.get.return_value = Response(200, payload={"status": "failed"})
    ctx = SourceContext(
        client=client, enterprise_name="enterprise", deployment_type="ghec"
    )

    assert (
        list(
            enterprise_credential_inventory.__wrapped__(SimpleNamespace(id="E_1"), ctx)
        )
        == []
    )
    assert "Credential export did not complete" in caplog.text
    client.post.assert_called_once()


def test_classic_pat_model_emits_owner_and_authorization_edges():
    token = ClassicPersonalAccessToken(
        credential_id=42,
        display_name="CI deploy",
        owner_id=7,
        owner_login="octocat",
        scopes=["repo"],
        credential_state="active",
        authorized_organizations=["acme", "ops"],
        enterprise_node_id="E_1",
        enterprise_name="enterprise",
    )
    lookup = MagicMock()
    lookup.enterprise_user_id_for_database_id.return_value = "U_1"
    lookup.enterprise_organization_id_for_login.side_effect = ["O_1", None]
    token._lookup = lookup

    assert token.as_node.properties.node_id == "GH_CLASSIC_PAT_E_1_42"
    edges = list(token.edges)
    assert [edge.kind for edge in edges] == [
        ek.CONTAINS,
        ek.HAS_PERSONAL_ACCESS_TOKEN,
        ek.AUTHORIZED_FOR_ORGANIZATION,
    ]
    assert edges[1].start.value == "U_1"
    assert edges[2].end.value == "O_1"


def test_inventory_owner_and_organization_resolve_to_graph_ids():
    member = BaseUser.model_validate(
        {
            "__typename": "User",
            "id": "U_1",
            "databaseId": 7,
            "login": "octocat",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        }
    )
    assert member.model_dump()["database_id"] == 7

    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.enterprise_users (id VARCHAR, database_id BIGINT)"
    )
    connection.execute("INSERT INTO github.enterprise_users VALUES ('U_1', 7)")
    connection.execute(
        "CREATE TABLE github.enterprise_organizations (id VARCHAR, login VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.enterprise_organizations VALUES ('O_1', 'Acme')"
    )
    lookup = GithubLookup(connection)

    assert lookup.enterprise_user_id_for_database_id(7) == "U_1"
    assert lookup.enterprise_organization_id_for_login("acme") == "O_1"
