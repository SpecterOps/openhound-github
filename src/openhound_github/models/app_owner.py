"""Identity-only App owners kept separate from tenant membership inventory."""

from dataclasses import dataclass

from openhound.core.asset import BaseAsset

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.main import app


OWNER_KINDS = {
    "User": "GH_User",
    "Organization": "GH_Organization",
    "Enterprise": "GH_Enterprise",
}


@dataclass
class GHAppOwnerProperties(GHNodeProperties):
    collected: bool = False
    login: str | None = None
    full_name: str | None = None
    description: str | None = None
    company: str | None = None
    url: str | None = None


@app.asset()
class AppOwner(BaseAsset):
    node_id: str
    login: str
    type: str
    name: str | None = None
    description: str | None = None
    company: str | None = None
    html_url: str | None = None

    @property
    def as_node(self):
        kind = OWNER_KINDS.get(self.type)
        if kind is None or self._lookup.app_owner_is_collected(self.node_id, self.type):
            return None
        return GHNode(
            kinds=[kind],
            properties=GHAppOwnerProperties(
                node_id=self.node_id,
                environmentid=self.node_id,
                name=self.login,
                displayname=self.name or self.login,
                login=self.login,
                full_name=self.name,
                description=self.description,
                company=self.company,
                url=self.html_url,
            ),
        )

    @property
    def edges(self):
        return []
