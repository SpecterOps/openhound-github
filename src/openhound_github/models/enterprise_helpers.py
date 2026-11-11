from openhound_github.enterprise_team_ids import (
    enterprise_team_node_id as enterprise_team_node_id,
)


def enterprise_role_node_id(enterprise_id: str, role_id: str | int) -> str:
    return f"GH_EnterpriseRole_{enterprise_id}_{role_id}"
