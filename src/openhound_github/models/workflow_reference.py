from collections.abc import Iterable, Iterator
from typing import Any

from openhound.core.models.entries_dataclass import PropertyMatch  # type: ignore[import-untyped]
from pydantic import BaseModel

from openhound_github.kinds import nodes as nk


class WorkflowReference(BaseModel):
    name: str
    context: str | None = None


def resolved_secret_targets(
    lookup: Any,
    references: Iterable[WorkflowReference],
    *,
    repository_node_id: str,
    org_login: str,
    org_node_id: str | None,
    environment: str | None,
) -> Iterator[tuple[str, list[PropertyMatch]]]:
    """Resolve statically referenced secret names to graph targets by scope."""
    for ref in references:
        if lookup.repo_secret(ref.name, repository_node_id):
            yield (
                nk.REPO_SECRET,
                [
                    PropertyMatch(key="name", value=ref.name.upper()),
                    PropertyMatch(key="repository_id", value=repository_node_id),
                ],
            )

        if lookup.org_secret(ref.name, org_login):
            yield (
                nk.ORG_SECRET,
                [
                    PropertyMatch(key="name", value=ref.name.upper()),
                    PropertyMatch(key="environmentid", value=org_node_id),
                ],
            )

        if environment and "${{" not in environment:
            if lookup.environment_secret_for_environment(
                ref.name, repository_node_id, environment
            ):
                yield (
                    nk.ENVIRONMENT_SECRET,
                    [
                        PropertyMatch(key="name", value=ref.name.upper()),
                        PropertyMatch(
                            key="deployment_environment_name",
                            value=environment,
                        ),
                        PropertyMatch(key="repository_id", value=repository_node_id),
                    ],
                )
