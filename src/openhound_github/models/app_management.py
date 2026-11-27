"""Compose App control from predefined role authority and registration ownership."""

from openhound.core.models.entries_dataclass import Edge, EdgePath

from openhound_github.graph import GHEdgeProperties
from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup


APP_MANAGEMENT_ROLES = {
    "Organization": ("GH_OrgRole", ("owners", "app_manager")),
    "Enterprise": ("GH_EnterpriseRole", ("owners", "enterprise_app_manager")),
}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def app_management_edges(
    lookup: GithubLookup,
    *,
    role_node_id: str,
    role_name: str,
    is_predefined: bool,
    account_node_id: str,
    account_type: str,
):
    """Yield role-to-App capabilities without expanding users or installations.

    Public per-App manager enumeration is not supplied by this helper. Personal
    ownership keeps its existing GH_Owns path. Account hierarchy, collection
    context, and installation targets do not confer registration control.
    """
    role_kind, names = APP_MANAGEMENT_ROLES[account_type]
    if not is_predefined or role_name not in names or not account_node_id:
        return
    role_id = _escape(role_node_id)
    account_id = _escape(account_node_id)
    role_names = ", ".join(f"'{name}'" for name in names)
    for (app_node_id,) in lookup.app_node_ids_owned_by(account_node_id, account_type):
        app_id = _escape(app_node_id)
        yield Edge(
            kind=ek.CAN_MANAGE_APP,
            start=EdgePath(value=role_node_id, match_by="id"),
            end=EdgePath(value=app_node_id, match_by="id"),
            properties=GHEdgeProperties(
                traversable=True,
                composed=True,
                reason="owner_role" if role_name == "owners" else "app_manager_role",
                query_composition=(
                    f"MATCH p=(role:{role_kind} {{node_id:'{role_id}'}})"
                    f"<-[:GH_Contains]-(account:GH_{account_type} {{node_id:'{account_id}'}})"
                    f"-[:GH_Owns]->(:GH_App {{node_id:'{app_id}'}}) "
                    f"WHERE role.short_name IN [{role_names}] "
                    "AND (role.source = 'Predefined' OR "
                    "(role.type = 'default' AND (role.source IS NULL OR role.source = 'Default'))) "
                    "RETURN p"
                ),
            ),
        )
