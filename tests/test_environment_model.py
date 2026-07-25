from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.environment import DeploymentBranchPolicy
from openhound_github.models.environment import Environment
from openhound_github.models.environment_branch_policy import EnvironmentBranchPolicy

def _make_environment() -> Environment:
    env = Environment(
        id=161088068,
        node_id="MDExOkVudmlyb25tZW50MTYxMDg4MDY4",
        name="staging",
        url="https://api.github.com/repos/github/hello-world/environments/staging",
        html_url="https://github.com/github/hello-world/deployments/activity_log?environments_filter=staging",
        created_at="2020-11-23T22:00:40Z",
        updated_at="2020-11-23T22:00:40Z",
        protection_rules=[
            {
                "id": 3736,
                "node_id": "MDQ6R2F0ZTM3MzY=",
                "type": "wait_timer",
                "wait_timer": 30,
            },
            {
                "id": 3755,
                "node_id": "MDQ6R2F0ZTM3NTU=",
                "prevent_self_review": False,
                "type": "required_reviewers",
                "reviewers": [
                    {
                        "type": "User",
                        "reviewer": {
                            "login": "octocat",
                            "id": 1,
                            "node_id": "MDQ6VXNlcjE=",
                            "avatar_url": "",
                            "gravatar_id": "",
                            "url": "",
                            "html_url": "",
                            "followers_url": "",
                            "following_url": "",
                            "gists_url": "",
                            "starred_url": "",
                            "subscriptions_url": "",
                            "organizations_url": "",
                            "repos_url": "",
                            "events_url": "",
                            "received_events_url": "",
                            "type": "User",
                            "site_admin": False,
                        },
                    },
                    {
                        "type": "Team",
                        "reviewer": {
                            "id": 1,
                            "node_id": "MDQ6VGVhbTE=",
                            "url": "",
                            "html_url": "",
                            "name": "Justice League",
                            "slug": "justice-league",
                            "description": "A great team.",
                            "privacy": "closed",
                            "notification_setting": "notifications_enabled",
                            "permission": "admin",
                            "members_url": "",
                            "repositories_url": "",
                            "parent": None,
                        },
                    },
                ],
            },
            {
                "id": 3756,
                "node_id": "MDQ6R2F0ZTM3NTY=",
                "type": "branch_policy",
            },
        ],
        deployment_branch_policy={
            "protected_branches": False,
            "custom_branch_policies": True,
        },
        org_login="github",
        repository_name="hello-world",
        repository_full_name="github/hello-world",
        repository_node_id="R_123",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_123"
    env._lookup = lookup
    return env

def _make_environment_branch_policy(name: str) -> EnvironmentBranchPolicy:
    return EnvironmentBranchPolicy(
        id=1,
        node_id="POLICY_1",
        name=name,
        environment_node_id="ENV_1",
        environment_name="production",
        repository_name="hello-world",
        repository_node_id="R_123",
        org_login="github",
    )

def test_environment_node_surfaces_protection_rule_properties() -> None:
    env = _make_environment()

    node = env.as_node

    assert node.properties.wait_timer == 30
    assert node.properties.prevent_self_review is False
    assert node.properties.reviewer_count == 2
    assert node.properties.custom_branch_policies is True
    assert node.properties.protected_branches is False


def test_environment_edges_include_required_reviewer_relationships() -> None:
    env = _make_environment()

    edges = list(env.edges)

    reviewer_edges = [edge for edge in edges if edge.kind == ek.APPROVES_DEPLOYMENT_TO]
    assert len(reviewer_edges) == 2
    assert {edge.start.value for edge in reviewer_edges} == {
        "MDQ6VXNlcjE=",
        "MDQ6VGVhbTE=",
    }

def test_environment_branch_policy_single_star_does_not_cross_slashes() -> None:
    policy = _make_environment_branch_policy("release/*")

    assert policy.matches_branch("release/v1") is True
    assert policy.matches_branch("release/v1/hotfix") is False
    assert policy.matches_branch("foo/bar") is False


def test_environment_branch_policy_double_star_crosses_slashes() -> None:
    policy = _make_environment_branch_policy("release/**/*")

    assert policy.matches_branch("release/v1/hotfix") is True
    assert policy.matches_branch("release/v1") is True
    assert policy.matches_branch("release/") is False

def test_protected_branches_only_without_any_bpr_allows_all_branches() -> None:
    env = _make_environment()
    env.deployment_branch_policy = DeploymentBranchPolicy(
        protected_branches=True,
        custom_branch_policies=False,
    )
    env._lookup.branches_with_bpr.return_value = []
    env._lookup.branches_for_repository.return_value = [
        ("B_main", "main", False),
        ("B_release", "release/v1", False),
    ]

    deploy_edges = [
        edge for edge in env.edges if edge.kind == ek.CAN_DEPLOY_TO_ENVIRONMENT
    ]

    assert {edge.start.value for edge in deploy_edges} == {
        "R_123",
        "B_main",
        "B_release",
    }
