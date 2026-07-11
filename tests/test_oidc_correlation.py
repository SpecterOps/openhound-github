import json

import pytest

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models.oidc import (
    GithubOidcCorrelation,
    iter_github_oidc_rows,
    parse_github_oidc_subject,
)


@pytest.mark.parametrize(
    ("subject", "target_type", "target_name"),
    [
        ("repo:acme/payments:*", "repository", None),
        (
            "repo:acme/payments:ref:refs/heads/main",
            "branch",
            "main",
        ),
        (
            "repo:acme/payments:environment:production",
            "environment",
            "production",
        ),
        ("repo:acme/payments:pull_request", "repository", None),
    ],
)
def test_parse_github_oidc_subject(
    subject: str, target_type: str, target_name: str | None
) -> None:
    parsed = parse_github_oidc_subject(subject)

    assert parsed is not None
    assert parsed.organization == "acme"
    assert parsed.repository == "payments"
    assert parsed.target_type == target_type
    assert parsed.target_name == target_name


def test_oidc_rows_filter_non_github_issuers_and_deduplicate(tmp_path) -> None:
    fic = {
        "id": "fic-1",
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "repo:acme/payments:*",
    }
    payload = {
        "data": [
            {
                "kind": "AZFederatedIdentityCredential",
                "data": {"fics": [{"fic": fic}, {"fic": fic}]},
            },
            {
                "kind": "AZFederatedIdentityCredential",
                "data": {
                    "fics": [
                        {
                            "fic": {
                                "id": "fic-2",
                                "issuer": "https://issuer.example.test",
                                "subject": "repo:acme/payments:*",
                            }
                        }
                    ]
                },
            },
        ]
    }
    path = tmp_path / "azurehound.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    rows = list(iter_github_oidc_rows(path))

    assert len(rows) == 1
    assert rows[0]["fic_id"] == "fic-1"


@pytest.mark.parametrize(
    ("target_type", "target_name", "start_kind", "expected_matchers"),
    [
        (
            "repository",
            None,
            nk.REPOSITORY,
            {"full_name": "acme/payments"},
        ),
        (
            "branch",
            "main",
            nk.BRANCH,
            {
                "repository_name": "payments",
                "short_name": "main",
                "environment_name": "acme",
            },
        ),
        (
            "environment",
            "production",
            nk.ENVIRONMENT,
            {
                "repository_name": "payments",
                "short_name": "production",
                "environment_name": "acme",
            },
        ),
    ],
)
def test_oidc_edge_matches_openhound_github_node_properties(
    target_type: str,
    target_name: str | None,
    start_kind: str,
    expected_matchers: dict[str, str],
) -> None:
    correlation = GithubOidcCorrelation(
        fic_id="fic-1",
        subject="repo:acme/payments:*",
        organization="acme",
        repository="payments",
        qualifier="*",
        target_type=target_type,
        target_name=target_name,
    )

    edge = next(iter(correlation.edges))

    assert edge.kind == ek.CAN_ASSUME_IDENTITY
    assert edge.start.kind == start_kind
    assert {matcher.key: matcher.value for matcher in edge.start.property_matchers} == expected_matchers
    assert edge.end.value == "fic-1"
    assert edge.properties.subject == "repo:acme/payments:*"
    assert edge.properties.traversable is True
