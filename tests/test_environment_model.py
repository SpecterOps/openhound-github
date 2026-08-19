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
    lookup.branches_with_bpr.return_value = []
    lookup.environment_branch_policy_names.return_value = []

    def reviewer_deployment_path(
        _reviewer_node_id,
        _reviewer_type,
        _repository_node_id,
        eligible_branch_ids,
        allow_create_branch,
    ):
        if allow_create_branch:
            return ("create_branch", None)
        if eligible_branch_ids:
            return ("write_branch", eligible_branch_ids[0])
        return None

    lookup.reviewer_deployment_path.side_effect = reviewer_deployment_path
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

def _make_unrestricted_environment() -> Environment:
    env = _make_environment()
    env.deployment_branch_policy = DeploymentBranchPolicy(
        protected_branches=False,
        custom_branch_policies=False,
    )
    env._lookup.branches_for_repository.return_value = [
        ("B_main", "main", False),
        ("B_release", "release/v1", False),
    ]
    return env


def _deploy_edges(env: Environment):
    return [edge for edge in env.edges if edge.kind == ek.CAN_DEPLOY_TO_ENVIRONMENT]


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


def test_environment_without_reviewers_emits_repository_and_branch_deploy_edges() -> None:
    env = _make_unrestricted_environment()
    env.protection_rules = []

    deploy_edges = _deploy_edges(env)

    assert {edge.start.value for edge in deploy_edges} == {
        "R_123",
        "B_main",
        "B_release",
    }


def test_environment_with_self_review_emits_only_reviewer_deploy_edges() -> None:
    env = _make_unrestricted_environment()

    deploy_edges = _deploy_edges(env)

    assert {edge.start.value for edge in deploy_edges} == {
        "MDQ6VXNlcjE=",
        "MDQ6VGVhbTE=",
    }
    assert all(edge.properties.composed for edge in deploy_edges)
    assert all(
        "coalesce(env.prevent_self_review, false) = false"
        in edge.properties.query_composition
        for edge in deploy_edges
    )
    assert all(
        "GH_CanCreateBranch" in edge.properties.query_composition
        for edge in deploy_edges
    )


def test_environment_reviewer_without_deployable_path_only_emits_approval_edge() -> None:
    env = _make_unrestricted_environment()
    env._lookup.reviewer_deployment_path.return_value = None
    env._lookup.reviewer_deployment_path.side_effect = None

    edges = list(env.edges)

    assert {
        edge.start.value
        for edge in edges
        if edge.kind == ek.APPROVES_DEPLOYMENT_TO
    } == {"MDQ6VXNlcjE=", "MDQ6VGVhbTE="}
    assert _deploy_edges(env) == []


def test_environment_reviewer_protected_branch_path_requires_eligible_branch() -> None:
    env = _make_environment()
    env.deployment_branch_policy = DeploymentBranchPolicy(
        protected_branches=True,
        custom_branch_policies=False,
    )
    env._lookup.branches_for_repository.return_value = [
        ("B_main", "main", True),
        ("B_release", "release/v1", False),
    ]
    env._lookup.branches_with_bpr.return_value = [("B_main",)]
    env._lookup.reviewer_deployment_path.return_value = ("write_branch", "B_main")
    env._lookup.reviewer_deployment_path.side_effect = None

    deploy_edges = _deploy_edges(env)

    assert {edge.start.value for edge in deploy_edges} == {
        "MDQ6VXNlcjE=",
        "MDQ6VGVhbTE=",
    }
    assert all(
        "GH_ProtectedBy" in edge.properties.query_composition
        for edge in deploy_edges
    )
    env._lookup.reviewer_deployment_path.assert_any_call(
        "MDQ6VXNlcjE=",
        "user",
        "R_123",
        ("B_main",),
        False,
    )


def test_environment_reviewer_custom_policy_uses_matching_branches() -> None:
    env = _make_environment()
    env._lookup.branches_for_repository.return_value = [
        ("B_main", "main", False),
        ("B_release", "release/v1", False),
    ]
    env._lookup.environment_branch_policy_names.return_value = [("release/*",)]
    env._lookup.reviewer_deployment_path.return_value = ("write_branch", "B_release")
    env._lookup.reviewer_deployment_path.side_effect = None

    deploy_edges = _deploy_edges(env)

    assert {edge.start.value for edge in deploy_edges} == {
        "MDQ6VXNlcjE=",
        "MDQ6VGVhbTE=",
    }
    assert all(
        "GH_MatchesEnvironmentPolicy" in edge.properties.query_composition
        for edge in deploy_edges
    )
    env._lookup.reviewer_deployment_path.assert_any_call(
        "MDQ6VXNlcjE=",
        "user",
        "R_123",
        ("B_release",),
        False,
    )


def test_environment_with_prevent_self_review_emits_no_direct_deploy_edges() -> None:
    env = _make_unrestricted_environment()
    env.protection_rules[1].prevent_self_review = True

    assert _deploy_edges(env) == []


def test_environment_with_prevent_self_review_keeps_admin_bypass_edge() -> None:
    env = _make_unrestricted_environment()
    env.protection_rules[1].prevent_self_review = True
    env.can_admins_bypass = True

    deploy_edges = _deploy_edges(env)

    assert {edge.start.value for edge in deploy_edges} == {"R_123_admin"}


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


def test_environment_branch_policy_with_reviewers_suppresses_branch_deploy_edges() -> None:
    policy = _make_environment_branch_policy("main")
    policy.required_reviewers = True
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_123"
    lookup.environment_deployment_branch_policy.return_value = (False, True)
    lookup.branches_for_repository.return_value = [("B_main", "main", False)]
    policy._lookup = lookup

    edges = list(policy.edges)

    assert any(edge.kind == ek.MATCHES_ENVIRONMENT_POLICY for edge in edges)
    assert not any(edge.kind == ek.CAN_DEPLOY_TO_ENVIRONMENT for edge in edges)


def test_environment_branch_policy_uses_environment_lookup_for_legacy_rows() -> None:
    policy = _make_environment_branch_policy("main")
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_123"
    lookup.environment_deployment_branch_policy.return_value = (False, True)
    lookup.environment_deployment_reviewer_policy.return_value = (True, False)
    lookup.branches_for_repository.return_value = [("B_main", "main", False)]
    policy._lookup = lookup

    edges = list(policy.edges)

    assert any(edge.kind == ek.MATCHES_ENVIRONMENT_POLICY for edge in edges)
    assert not any(edge.kind == ek.CAN_DEPLOY_TO_ENVIRONMENT for edge in edges)


def test_protected_branches_only_without_any_bpr_allows_all_branches() -> None:
    env = _make_environment()
    env.protection_rules = []
    env.deployment_branch_policy = DeploymentBranchPolicy(
        protected_branches=True,
        custom_branch_policies=False,
    )
    env._lookup.branches_with_bpr.return_value = []
    env._lookup.branches_for_repository.return_value = [
        ("B_main", "main", False),
        ("B_release", "release/v1", False),
    ]

    deploy_edges = _deploy_edges(env)

    assert {edge.start.value for edge in deploy_edges} == {
        "R_123",
        "B_main",
        "B_release",
    }
