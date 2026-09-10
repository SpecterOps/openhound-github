from dataclasses import dataclass, field

from openhound.core.models.entries_dataclass import EdgeProperties
from openhound.core.models.entries_dataclass import Node as BaseNode
from openhound.core.models.entries_dataclass import NodeProperties as BaseProperties

GITHUB_SOURCE_KIND = "GitHub"
SAML_SOURCE_KIND = "SAML"


@dataclass
class GHNodeProperties(BaseProperties):
    """Extends the base with GitHub's native node_id as the authoritative identifier."""

    node_id: str


@dataclass
class GHNode(BaseNode):
    properties: GHNodeProperties  # type: ignore[assignment]
    kinds: list[str]
    id: str = field(init=False)

    def __post_init__(self):
        # Use GitHub's native node_id as the OpenGraph node id so edges can
        # reference nodes by the same identifier used during collection.
        self.id = self.properties.node_id
        source_kind = (
            SAML_SOURCE_KIND
            if any(kind.startswith("SAML_") for kind in self.kinds)
            else GITHUB_SOURCE_KIND
        )
        if source_kind not in self.kinds:
            self.kinds.append(source_kind)


@dataclass
class GHEdgeProperties(EdgeProperties):
    """Extends EdgeProperties with optional composition query and reason."""

    query_composition: str | None = None
    reason: str | None = None
