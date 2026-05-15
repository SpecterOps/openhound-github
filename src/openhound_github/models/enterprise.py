from dataclasses import dataclass
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, NodeDef
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHEnterpriseProperties(GHNodeProperties):
    """Properties for a GitHub enterprise.

    Attributes:
        collected: Whether this node was collected directly.
        slug: The enterprise slug.
        enterprise_name: The enterprise display name.
        description: The enterprise description.
        location: The enterprise location.
        url: The enterprise GitHub URL.
        website_url: The enterprise website URL.
        created_at: When the enterprise was created.
        updated_at: When the enterprise was last updated.
        billing_email: The enterprise billing email.
        security_contact_email: The enterprise security contact email.
        viewer_is_admin: Whether the authenticated viewer is an enterprise admin.
        environment_name: The enterprise environment name.
        query_organizations: Query for contained organizations.
    """

    collected: bool = True
    slug: str | None = None
    enterprise_name: str | None = None
    description: str | None = None
    location: str | None = None
    url: str | None = None
    website_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    billing_email: str | None = None
    security_contact_email: str | None = None
    viewer_is_admin: bool | None = None
    environment_name: str | None = None
    query_organizations: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE,
        description="GitHub Enterprise",
        icon="globe",
        properties=GHEnterpriseProperties,
    ),
)
class Enterprise(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: str
    database_id: int | None = Field(alias="databaseId", default=None)
    name: str | None = None
    slug: str
    description: str | None = None
    location: str | None = None
    url: str | None = None
    website_url: str | None = Field(alias="websiteUrl", default=None)
    created_at: str | None = Field(alias="createdAt", default=None)
    updated_at: str | None = Field(alias="updatedAt", default=None)
    billing_email: str | None = Field(alias="billingEmail", default=None)
    security_contact_email: str | None = Field(
        alias="securityContactEmail", default=None
    )
    viewer_is_admin: bool | None = Field(alias="viewerIsAdmin", default=None)
    organizations: dict | None = Field(default_factory=dict)

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE],
            properties=GHEnterpriseProperties(
                name=self.slug,
                displayname=self.name or self.slug,
                node_id=self.node_id,
                environmentid=self._lookup.enterprise_id(),
                environment_name=self.slug,
                slug=self.slug,
                enterprise_name=self.name,
                description=self.description,
                location=self.location,
                url=self.url,
                website_url=self.website_url,
                created_at=self.created_at,
                updated_at=self.updated_at,
                billing_email=self.billing_email,
                security_contact_email=self.security_contact_email,
                viewer_is_admin=self.viewer_is_admin,
                query_organizations=f"MATCH p=(:GH_Enterprise {{node_id:'{self.node_id}'}})-[:GH_Contains]->(:GH_Organization) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []
