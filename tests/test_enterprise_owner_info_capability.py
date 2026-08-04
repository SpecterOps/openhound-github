"""Regression coverage for GitHub's App-only enterprise ownerInfo gap."""

import inspect
import logging
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise_admins,
    enterprise_external_identities,
    enterprise_saml_provider,
)


def _owner_info_null_client() -> MagicMock:
    client = MagicMock()
    client.paginate.return_value = [[{"enterprise": {"ownerInfo": None}}]]
    return client


def _run(transformer, enterprise, ctx):
    return list(inspect.unwrap(transformer._pipe.gen)(enterprise, ctx))


def test_enterprise_app_owner_info_gap_is_warned_once(caplog) -> None:
    client = _owner_info_null_client()
    ctx = SourceContext(
        client=client,
        enterprise_name="example-enterprise",
        auth_kind="enterprise_app",
    )
    enterprise = SimpleNamespace(id="ENT_1")

    with caplog.at_level(
        logging.WARNING, logger="openhound_github.resources.enterprise"
    ):
        admins = _run(enterprise_admins, enterprise, ctx)
        saml = _run(enterprise_saml_provider, enterprise, ctx)

    assert admins == []
    assert saml == []
    matching = [
        message
        for message in caplog.messages
        if "enterprise ownerInfo as null for enterprise App auth" in message
    ]
    assert len(matching) == 1
    assert "Enterprise owners" in matching[0]
    assert "enterprise SAML external identities" in matching[0]
    assert "credentials.owner_info_token" in matching[0]
    assert "read:enterprise" in matching[0]


def test_enterprise_app_uses_owner_info_token_client() -> None:
    app_client = MagicMock()
    owner_info_client = MagicMock()
    owner_info_client.paginate.side_effect = [
        [
            [
                {
                    "enterprise": {
                        "ownerInfo": {
                            "admins": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "U_1",
                                            "login": "enterprise-owner",
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            ]
        ],
        [
            [
                {
                    "enterprise": {
                        "ownerInfo": {
                            "samlIdentityProvider": {
                                "id": "IDP_1",
                                "issuer": "https://idp.example.test",
                                "ssoUrl": "https://idp.example.test/sso",
                                "externalIdentities": {"nodes": []},
                            }
                        }
                    }
                }
            ]
        ],
        [
            [
                {
                    "enterprise": {
                        "ownerInfo": {
                            "samlIdentityProvider": {
                                "externalIdentities": {"nodes": []}
                            }
                        }
                    }
                }
            ]
        ],
    ]
    ctx = SourceContext(
        client=app_client,
        owner_info_client=owner_info_client,
        enterprise_name="example-enterprise",
        auth_kind="enterprise_app",
    )

    admins = _run(enterprise_admins, SimpleNamespace(id="ENT_1"), ctx)
    saml_providers = _run(enterprise_saml_provider, SimpleNamespace(id="ENT_1"), ctx)
    external_identities = _run(
        enterprise_external_identities,
        SimpleNamespace(
            id="IDP_1",
            issuer="https://idp.example.test",
            sso_url="https://idp.example.test/sso",
            enterprise_node_id="ENT_1",
            enterprise_slug="example-enterprise",
            github_deployment_id="github.com",
        ),
        ctx,
    )

    assert admins == [
        {
            "node_id": "U_1",
            "login": "enterprise-owner",
            "assignment": "direct",
            "role_id": "owners",
            "enterprise_node_id": "ENT_1",
            "enterprise_slug": "example-enterprise",
        }
    ]
    assert saml_providers[0]["id"] == "IDP_1"
    assert external_identities == []
    assert owner_info_client.paginate.call_count == 3
    app_client.paginate.assert_not_called()


def test_enterprise_app_wires_owner_info_token_client(monkeypatch) -> None:
    source_module = import_module("openhound_github.source")
    captured = {}
    real_enterprise_resources = source_module.enterprise_resources

    def capture_context(ctx):
        captured["ctx"] = ctx
        return real_enterprise_resources(ctx)

    monkeypatch.setattr(source_module, "enterprise_resources", capture_context)
    monkeypatch.setattr(
        source_module,
        "GithubApp",
        lambda **_kwargs: SimpleNamespace(installations=[]),
    )
    monkeypatch.setenv("SOURCES__GITHUB__CREDENTIALS__CLIENT_ID", "Iv1.example")
    monkeypatch.setenv("SOURCES__GITHUB__CREDENTIALS__KEY_PATH", "unused.pem")
    monkeypatch.setenv(
        "SOURCES__GITHUB__CREDENTIALS__ENTERPRISE_NAME", "example-enterprise"
    )
    monkeypatch.setenv(
        "SOURCES__GITHUB__CREDENTIALS__OWNER_INFO_TOKEN", "not-a-real-token"
    )

    source_module.source()

    assert captured["ctx"].auth_kind == "enterprise_app"
    assert captured["ctx"].owner_info_client is not None


def test_owner_token_gap_has_actionable_scope_warning(caplog) -> None:
    ctx = SourceContext(
        client=_owner_info_null_client(),
        enterprise_name="example-enterprise",
        auth_kind="token",
    )

    with caplog.at_level(
        logging.WARNING, logger="openhound_github.resources.enterprise"
    ):
        assert _run(enterprise_admins, SimpleNamespace(id="ENT_1"), ctx) == []

    assert any(
        "credential belongs to an enterprise owner and has read:enterprise" in message
        for message in caplog.messages
    )
