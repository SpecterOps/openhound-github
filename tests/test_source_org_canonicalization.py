import importlib
import inspect

import pytest

from openhound_github.resources.organization import organizations
from openhound_github.source import (
    GithubOrgAppCredentials,
    GithubTokenCredentials,
    OrgContext,
    SourceContext,
    _canonicalize_org_names,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payloads: dict[str, dict]):
        self.payloads = payloads
        self.get_calls: list[str] = []

    def get(self, path: str) -> _FakeResponse:
        self.get_calls.append(path)
        return _FakeResponse(self.payloads[path])


def test_canonicalize_org_names_rewrites_org_context_and_caches_response() -> None:
    client = _FakeClient(
        {
            "/orgs/spectertst": {
                "login": "SpecterTst",
                "node_id": "O_kgDOCoV2OQ",
            }
        }
    )
    ctx = SourceContext(
        organizations=[OrgContext(client=client, org_name="spectertst")]
    )

    _canonicalize_org_names(ctx)

    assert ctx.organizations[0].org_name == "SpecterTst"
    assert ctx.organizations_cache == {
        "SpecterTst": {
            "login": "SpecterTst",
            "node_id": "O_kgDOCoV2OQ",
        }
    }


def test_organizations_reuses_preflight_org_response() -> None:
    client = _FakeClient(
        {
            "/orgs/spectertst": {
                "login": "SpecterTst",
                "node_id": "O_kgDOCoV2OQ",
            },
            "/orgs/SpecterTst/actions/permissions": {},
            "/orgs/SpecterTst/actions/permissions/self-hosted-runners": {},
            "/orgs/SpecterTst/actions/permissions/workflow": {},
        }
    )
    ctx = SourceContext(
        organizations=[OrgContext(client=client, org_name="spectertst")]
    )

    _canonicalize_org_names(ctx)
    rows = list(inspect.unwrap(organizations._pipe.gen)(ctx))

    assert rows[0]["login"] == "SpecterTst"
    assert client.get_calls == [
        "/orgs/spectertst",
        "/orgs/SpecterTst/actions/permissions",
        "/orgs/SpecterTst/actions/permissions/self-hosted-runners",
        "/orgs/SpecterTst/actions/permissions/workflow",
    ]


@pytest.mark.parametrize(
    "credentials",
    (
        GithubTokenCredentials(token="token", org_name="spectertst"),
        GithubOrgAppCredentials(
            client_id="Iv1.client-id",
            install_id="12345",
            key_path="/tmp/github-app.pem",
            org_name="spectertst",
        ),
    ),
)
def test_org_only_sources_canonicalize_before_resource_fanout(
    monkeypatch: pytest.MonkeyPatch,
    credentials,
) -> None:
    source_module = importlib.import_module("openhound_github.source")
    captured_ctx: dict[str, SourceContext] = {}

    class FakeRESTClient:
        def __init__(self, **kwargs) -> None:
            pass

        def get(self, path: str) -> _FakeResponse:
            assert path == "/orgs/spectertst"
            return _FakeResponse({"login": "SpecterTst", "node_id": "O_kgDOCoV2OQ"})

    monkeypatch.setattr(source_module, "RESTClient", FakeRESTClient)
    monkeypatch.setattr(source_module, "GithubInstallation", lambda **_: object())
    monkeypatch.setattr(
        source_module, "GitHubAppInstallationAuth", lambda **_: object()
    )

    def fake_organization_resources(ctx: SourceContext):
        captured_ctx["ctx"] = ctx
        return ()

    monkeypatch.setattr(
        source_module, "organization_resources", fake_organization_resources
    )

    resources = source_module.source.__wrapped__(
        credentials=credentials,
        host="https://api.github.com",
        emit_legacy_scim_correlations=False,
    )

    assert resources == ()
    assert captured_ctx["ctx"].organizations[0].org_name == "SpecterTst"
    assert (
        captured_ctx["ctx"].organizations_cache["SpecterTst"]["node_id"]
        == "O_kgDOCoV2OQ"
    )
