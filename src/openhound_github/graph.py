from dataclasses import dataclass, field

from openhound.core.models.entries_dataclass import EdgeProperties
from openhound.core.models.entries_dataclass import Node as BaseNode
from openhound.core.models.entries_dataclass import NodeProperties as BaseProperties


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


@dataclass
class GHEdgeProperties(EdgeProperties):
    """Extends EdgeProperties with optional composition query and reason."""

    query_composition: str | None = None
    reason: str | None = None
