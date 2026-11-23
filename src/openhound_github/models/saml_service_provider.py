from collections.abc import Iterable
from dataclasses import replace

from openhound.core.asset import BaseAsset
from openhound.core.models.entries_dataclass import Edge, EdgePath
from openhound_saml_producer import (
    NODE_DEFS,
    IssuerFact,
    SamlNode,
    ServiceProviderFact,
    edge_defs,
)
from openhound_saml_producer.contract import NodeKind
from openhound_saml_producer.sp import service_provider_edges, service_provider_node

from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from .saml_producer import (
    SAML,
    log_warnings,
    route_fact,
    service_provider_fact,
)

from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    normalize_scope_type,
)


@app.asset(
    node=NODE_DEFS[NodeKind.SERVICE_PROVIDER],
    edges=edge_defs(
        NodeKind.SERVICE_PROVIDER,
        native_kind=nk.SAML_IDENTITY_PROVIDER,
        account_kinds=[nk.USER],
    ),
)
class SamlServiceProvider(BaseAsset):
    """The SAML service provider of one GitHub organization or enterprise.

    The edges to the issuer and the ACS route come from this asset, so the
    shared issuer and ACS assets write nodes only. `SAML_HasAccount` edges come
    from the external identity asset, which holds each account's evidence.
    """

    id: str
    issuer: str | None = None
    environment_node_id: str
    environment_name: str
    environment_slug: str
    environment_type: str
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

    @property
    def as_node(self) -> SamlNode:
        return service_provider_node(SAML, self._fact())

    @property
    def edges(self) -> Iterable[Edge]:
        edges, warnings = service_provider_edges(
            SAML,
            self._fact(),
            native=EdgePath(value=self.id, match_by="id"),
            trusted_issuer=IssuerFact(entity_id=self.issuer) if self.issuer else None,
            routes=[
                route_fact(
                    self.environment_type,
                    self.environment_slug,
                    self.github_web_origin,
                )
            ],
        )
        log_warnings(warnings)
        return edges

    def _fact(self) -> ServiceProviderFact:
        fact = service_provider_fact(
            saml_provider_id=self.id,
            environment_node_id=self.environment_node_id,
            environment_name=self.environment_name,
            environment_type=self.environment_type,
            environment_slug=self.environment_slug,
            github_deployment_id=self.github_deployment_id,
        )
        return replace(
            fact,
            extras={
                "github_scope_type": normalize_scope_type(self.environment_type),
                "github_scope_slug": self.environment_slug,
                "github_deployment_id": self.github_deployment_id,
                "github_web_origin": self.github_web_origin,
            },
        )
