from collections.abc import Iterable

from openhound.core.asset import BaseAsset
from openhound.core.models.entries_dataclass import Edge
from openhound_saml_producer import NODE_DEFS, IssuerFact, SamlNode
from openhound_saml_producer.contract import NodeKind
from openhound_saml_producer.shared import issuer_node

from openhound_github.main import app
from .saml_producer import SAML

from .saml_helpers import DEFAULT_GITHUB_DEPLOYMENT_ID, DEFAULT_GITHUB_WEB_ORIGIN


@app.asset(node=NODE_DEFS[NodeKind.ISSUER])
class SamlIssuer(BaseAsset):
    """The shared SAML issuer that a GitHub scope trusts.

    The service provider asset writes the `SAML_TrustsIssuer` edge. Only
    `issuer` and `environment_node_id` reach the node. The other fields stay for
    the shape of previously collected rows.
    """

    issuer: str
    environment_slug: str
    environment_type: str
    environment_node_id: str
    environment_name: str | None = None
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

    @property
    def as_node(self) -> SamlNode:
        return issuer_node(
            SAML, self.environment_node_id, IssuerFact(entity_id=self.issuer)
        )

    @property
    def edges(self) -> Iterable[Edge]:
        return ()
