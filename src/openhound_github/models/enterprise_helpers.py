def enterprise_team_node_id(enterprise_id: str, team_id: str | int) -> str:
    return f"GH_EnterpriseTeam_{enterprise_id}_{team_id}"


def projected_enterprise_team_node_id(org_id: str | None, team_node_id: str) -> str:
    return f"GH_Team_{org_id}_{team_node_id}"


def enterprise_role_node_id(enterprise_id: str, role_id: str | int) -> str:
    return f"GH_EnterpriseRole_{enterprise_id}_{role_id}"
