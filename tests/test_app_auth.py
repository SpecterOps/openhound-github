from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from dlt.common.configuration.resolve import resolve_configuration

from openhound_github import auth
from openhound_github.auth import (
    AccountConfig,
    GithubSession,
    InstallationResponse,
    resolve_github_app_jwt_issuer,
)
from openhound_github.source import GithubEnterpriseAppCredentials


@pytest.mark.parametrize(
    ("client_id", "app_id", "expected"),
    (
        ("Iv1.client-id", None, "Iv1.client-id"),
        (None, "123456", "123456"),
        ("Iv1.preferred", "123456", "Iv1.preferred"),
        (" Iv1.trimmed ", "123456", "Iv1.trimmed"),
    ),
)
def test_resolve_github_app_jwt_issuer_prefers_client_id(
    client_id: str | None,
    app_id: str | None,
    expected: str,
) -> None:
    assert resolve_github_app_jwt_issuer(client_id=client_id, app_id=app_id) == expected


def test_resolve_github_app_jwt_issuer_requires_an_identifier() -> None:
    with pytest.raises(
        ValueError,
        match="require either client_id or app_id for the JWT issuer",
    ):
        resolve_github_app_jwt_issuer(client_id=None, app_id=None)


@pytest.mark.parametrize(
    ("client_id", "app_id"),
    (("Iv1.client-id", None), (None, "123456")),
)
def test_enterprise_app_configuration_accepts_either_identifier(
    client_id: str | None,
    app_id: str | None,
) -> None:
    credentials = resolve_configuration(
        GithubEnterpriseAppCredentials(
            client_id=client_id,
            app_id=app_id,
            key_path="/tmp/github-app.pem",
            enterprise_name="example-enterprise",
        )
    )

    assert credentials.is_partial() is False


def test_github_session_uses_explicit_jwt_issuer(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    key_path = tmp_path / "github-app.pem"
    key_path.write_text("test-private-key", encoding="utf-8")
    captured_claims: dict[str, object] = {}

    monkeypatch.setattr(auth.RSAKey, "import_key", lambda _: object())

    def fake_encode(header, claims, key):
        captured_claims.update(claims)
        return "encoded-jwt"

    monkeypatch.setattr(auth.jwt, "encode", fake_encode)

    session = GithubSession(
        jwt_issuer="123456",
        private_key_path=str(key_path),
    )

    assert session.jwt == "encoded-jwt"
    assert captured_claims["iss"] == "123456"


def test_legacy_installation_response_does_not_require_client_id() -> None:
    installation = InstallationResponse(
        id=42,
        account=AccountConfig(id=7, login="example-org"),
        target_type="Organization",
        app_id=123456,
    )

    assert installation.client_id is None
    assert installation.app_id == 123456


def test_enterprise_source_reuses_selected_issuer_for_installation_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_module = importlib.import_module("openhound_github.source")
    captured_issuers: list[str] = []

    class FakeGithubApp:
        def __init__(self, jwt_issuer: str, private_key_path: str) -> None:
            captured_issuers.append(jwt_issuer)
            self.installations = (
                SimpleNamespace(
                    id=11,
                    target_type="Organization",
                    account=SimpleNamespace(login="example-org"),
                ),
                SimpleNamespace(
                    id=12,
                    target_type="Enterprise",
                    account=SimpleNamespace(slug="example-enterprise"),
                ),
            )

    class FakeGithubInstallation:
        def __init__(
            self,
            installation_id: int,
            jwt_issuer: str,
            private_key_path: str,
        ) -> None:
            captured_issuers.append(jwt_issuer)

    class FakeRESTClient:
        def __init__(self, **kwargs) -> None:
            pass

    monkeypatch.setattr(source_module, "GithubApp", FakeGithubApp)
    monkeypatch.setattr(source_module, "GithubInstallation", FakeGithubInstallation)
    monkeypatch.setattr(
        source_module, "GitHubAppInstallationAuth", lambda **_: object()
    )
    monkeypatch.setattr(source_module, "RESTClient", FakeRESTClient)
    monkeypatch.setattr(source_module, "enterprise_resources", lambda _: ())
    monkeypatch.setattr(source_module, "organization_resources", lambda _: ())

    resources = source_module.source.__wrapped__(
        credentials=GithubEnterpriseAppCredentials(
            app_id="123456",
            key_path="/tmp/github-app.pem",
            enterprise_name="example-enterprise",
        ),
        host="https://api.github.com",
        collect_enterprise_scim=False,
        emit_legacy_scim_correlations=False,
    )

    assert resources == ()
    assert captured_issuers == ["123456", "123456", "123456"]
