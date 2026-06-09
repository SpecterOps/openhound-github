def enterprise_team_node_id(enterprise_id: str, team_id: str | int) -> str:
    return f"GH_EnterpriseTeam_{enterprise_id}_{team_id}"


def enterprise_role_node_id(enterprise_id: str, role_id: str | int) -> str:
    return f"GH_EnterpriseRole_{enterprise_id}_{role_id}"
