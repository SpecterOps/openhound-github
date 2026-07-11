"""Temporary GitHub-to-Azure OIDC correlation support.

AzureHound remains authoritative for AZFederatedIdentityCredential nodes. This
asset only materializes GH_CanAssumeIdentity relationships from AzureHound CE
JSON until a dedicated hybrid identity correlator owns cross-source matching.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import (
    ConditionalEdgePath,
    Edge,
    EdgePath,
    PropertyMatch,
)
from pydantic import ConfigDict

from openhound_github.graph import GHOidcEdgeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

logger = logging.getLogger(__name__)
GITHUB_ACTIONS_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_SUBJECT_RE = re.compile(r"^repo:([^/]+)/([^:]+):(.+)$")


@dataclass(frozen=True)
class ParsedGithubOidcSubject:
    organization: str
    repository: str
    qualifier: str
    target_type: Literal["repository", "branch", "environment"]
    target_name: str | None = None


def parse_github_oidc_subject(subject: str) -> ParsedGithubOidcSubject | None:
    match = OIDC_SUBJECT_RE.match(subject)
    if not match:
        return None
    organization, repository, qualifier = match.groups()
    branch_prefix = "ref:refs/heads/"
    environment_prefix = "environment:"
    if qualifier.startswith(branch_prefix):
        branch = qualifier[len(branch_prefix) :]
        if not branch:
            return None
        return ParsedGithubOidcSubject(
            organization, repository, qualifier, "branch", branch
        )
    if qualifier.startswith(environment_prefix):
        environment = qualifier[len(environment_prefix) :]
        if not environment:
            return None
        return ParsedGithubOidcSubject(
            organization, repository, qualifier, "environment", environment
        )
    return ParsedGithubOidcSubject(
        organization, repository, qualifier, "repository"
    )


def iter_github_oidc_rows(path: str | Path) -> Iterable[dict[str, str]]:
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"AzureHound input does not exist: {source_path}")
    with source_path.open(encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)

    seen: set[tuple[str, str]] = set()
    for entry in payload.get("data", []):
        if entry.get("kind") != nk.AZ_FEDERATED_IDENTITY_CREDENTIAL:
            continue
        for wrapper in (entry.get("data") or {}).get("fics") or []:
            fic = wrapper.get("fic") or {}
            subject = fic.get("subject")
            fic_id = fic.get("id")
            if fic.get("issuer") != GITHUB_ACTIONS_ISSUER or not subject or not fic_id:
                continue
            parsed = parse_github_oidc_subject(str(subject))
            if not parsed:
                logger.warning("Skipping malformed GitHub OIDC subject: %s", subject)
                continue
            key = (str(fic_id), str(subject))
            if key in seen:
                continue
            seen.add(key)
            yield {
                "fic_id": str(fic_id),
                "subject": str(subject),
                "organization": parsed.organization,
                "repository": parsed.repository,
                "qualifier": parsed.qualifier,
                "target_type": parsed.target_type,
                "target_name": parsed.target_name,
            }


@app.asset(
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.AZ_FEDERATED_IDENTITY_CREDENTIAL,
            kind=ek.CAN_ASSUME_IDENTITY,
            description="GitHub repository workflow can assume Azure federated identity",
            traversable=True,
        ),
        EdgeDef(
            start=nk.BRANCH,
            end=nk.AZ_FEDERATED_IDENTITY_CREDENTIAL,
            kind=ek.CAN_ASSUME_IDENTITY,
            description="GitHub branch workflow can assume Azure federated identity",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ENVIRONMENT,
            end=nk.AZ_FEDERATED_IDENTITY_CREDENTIAL,
            kind=ek.CAN_ASSUME_IDENTITY,
            description="GitHub environment workflow can assume Azure federated identity",
            traversable=True,
        ),
    ]
)
class GithubOidcCorrelation(BaseAsset):
    # DLT rehydrates raw rows with its own _dlt_id/_dlt_load_id metadata.
    model_config = ConfigDict(extra="allow")

    fic_id: str
    subject: str
    organization: str
    repository: str
    qualifier: str
    target_type: Literal["repository", "branch", "environment"]
    target_name: str | None = None

    @property
    def as_node(self):
        return None

    @property
    def start_path(self) -> ConditionalEdgePath:
        if self.target_type == "repository":
            return ConditionalEdgePath(
                kind=nk.REPOSITORY,
                property_matchers=[
                    PropertyMatch(
                        key="full_name",
                        value=f"{self.organization}/{self.repository}",
                    )
                ],
            )
        matchers = [
            PropertyMatch(key="repository_name", value=self.repository),
            PropertyMatch(key="short_name", value=self.target_name or ""),
            PropertyMatch(key="environment_name", value=self.organization),
        ]
        return ConditionalEdgePath(
            kind=nk.BRANCH if self.target_type == "branch" else nk.ENVIRONMENT,
            property_matchers=matchers,
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CAN_ASSUME_IDENTITY,
            start=self.start_path,
            end=EdgePath(value=self.fic_id, match_by="id"),
            properties=GHOidcEdgeProperties(
                traversable=True,
                subject=self.subject,
            ),
        )
