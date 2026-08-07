def runner_group_node_id(scope_node_id: str | None, runner_group_id: int) -> str:
    return f"{scope_node_id}_runner_group_{runner_group_id}"


def runner_node_id(scope_node_id: str | None, runner_id: int) -> str:
    return f"{scope_node_id}_runner_{runner_id}"
