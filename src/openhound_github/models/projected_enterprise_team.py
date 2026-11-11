from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset
from pydantic import ConfigDict, Field

from openhound_github.main import app


@app.asset(
    description="Native enterprise-team identity observed through an organization"
)
class ProjectedEnterpriseTeam(BaseAsset):
    """Raw identity observations only; do not emit organization-specific nodes."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    node_id: str
    id: int | None = None
    name: str
    slug: str
    description: str | None = None
    privacy: str | None = Field(default=None)
    org_login: str

    @property
    def as_node(self):
        """Retain the REST observation as lookup evidence without emitting a node."""
        return None

    @property
    def edges(self):
        return []
