from datetime import datetime

from openhound_github.kinds import edges as ek
from openhound_github.models.repository_variable import RepoVariable


def test_repository_variable_access_edge_is_traversable() -> None:
    variable = RepoVariable(
        name="DEPLOY_TARGET",
        value="prod",
        created_at=datetime.now(),
        org_login="acme",
        repository_name="repo",
        repository_node_id="R_1",
    )

    edge = next(edge for edge in variable.edges if edge.kind == ek.HAS_VARIABLE)

    assert edge.properties.traversable is True
