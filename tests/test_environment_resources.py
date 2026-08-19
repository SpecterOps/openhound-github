from types import SimpleNamespace

import pytest

from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    environment_branch_policies,
    environment_secrets,
    environment_variables,
)


class _FakeClient:
    def __init__(self):
        self.paginate_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter([])


def _ctx(client: _FakeClient) -> SourceContext:
    return SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="acme")],
    )


def _environment(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        node_id="ENV_1",
        org_login="acme",
        repository_name="repo",
        repository_full_name="acme/repo",
        repository_node_id="REPO_1",
        has_custom_branch_policies=True,
        required_reviewers=False,
        prevent_self_review=False,
    )


@pytest.mark.parametrize(
    ("transformer", "suffix"),
    [
        (environment_variables, "variables"),
        (environment_secrets, "secrets"),
        (environment_branch_policies, "deployment-branch-policies"),
    ],
)
@pytest.mark.parametrize(
    ("environment_name", "encoded_name"),
    [
        ("feature/test", "feature%2Ftest"),
        ("QA Environment", "QA%20Environment"),
        (
            "PCF_PROD_Deployment / deploy-PROD",
            "PCF_PROD_Deployment%20%2F%20deploy-PROD",
        ),
    ],
)
def test_environment_child_resources_encode_environment_names_in_paths(
    transformer, suffix: str, environment_name: str, encoded_name: str
) -> None:
    client = _FakeClient()

    rows = list(transformer.__wrapped__(_environment(environment_name), _ctx(client)))

    assert rows == []
    assert client.paginate_calls == [
        (f"/repos/acme/repo/environments/{encoded_name}/{suffix}", {})
    ]
