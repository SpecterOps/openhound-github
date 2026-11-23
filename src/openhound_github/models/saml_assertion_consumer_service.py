from collections.abc import Iterable

from openhound.core.asset import BaseAsset
from openhound.core.models.entries_dataclass import Edge
from openhound_saml_producer import NODE_DEFS, SamlNode
from openhound_saml_producer.contract import NodeKind
from openhound_saml_producer.shared import acs_node

from openhound_github.main import app
from .saml_producer import SAML, route_fact

from .saml_helpers import DEFAULT_GITHUB_DEPLOYMENT_ID, DEFAULT_GITHUB_WEB_ORIGIN


@app.asset(node=NODE_DEFS[NodeKind.ASSERTION_CONSUMER_SERVICE])
class SamlAssertionConsumerService(BaseAsset):
    """The shared SAML assertion consumer route of a GitHub scope.

    The service provider asset writes the `SAML_HasAssertionConsumerService`
    edge. The route comes from the scope and the web origin.
    """

    environment_slug: str
    environment_type: str
    environment_node_id: str
    environment_name: str | None = None
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

    @property
    def as_node(self) -> SamlNode:
        return acs_node(
            SAML,
            self.environment_node_id,
            route_fact(
                self.environment_type, self.environment_slug, self.github_web_origin
            ),
        )

    @property
    def edges(self) -> Iterable[Edge]:
        return ()
