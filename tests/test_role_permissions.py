from role_id_helpers import configure_role_ids, repo_role_id
from copy import deepcopy
from importlib.resources import files
import json

import pytest

from openhound_github.models import role_permissions as catalog


def snapshot():
    return json.loads(
        files("openhound_github").joinpath("data/role_permissions.json").read_text()
    )


def flattened(groups):
    return {permission for values in groups.values() for permission in values}


def test_classification_uses_native_targets_and_preserves_unknown_actions():
    result = catalog.split_role_permissions(
        [
            "read_repo_contents",
            "manage_org_security_products",
            "manage_enterprise_security_products",
            "read_package",
            "write_team_post",
            "read_project",
            "organization_future_permission",
            "contents:write",
            "read_repo_contents",
        ]
    )
    assert result == {
        "permissions_repository": ["read_repo_contents"],
        "permissions_organization": ["manage_org_security_products"],
        "permissions_enterprise": ["manage_enterprise_security_products"],
        "permissions_unclassified": [
            "contents:write",
            "organization_future_permission",
            "read_package",
            "read_project",
            "write_team_post",
        ],
    }
    assert catalog.permission_target_type("read_package") == "Package"
    assert catalog.permission_target_type("contents:write") is None


@pytest.mark.parametrize(
    "role,base,direct_count", [("triage", "read", 24), ("maintain", "write", 14)]
)
def test_repository_roles_keep_only_permissions_beyond_their_declared_base(
    role, base, direct_count
):
    definitions = {r["name"]: r for r in snapshot()["system_roles"]}
    direct = flattened(catalog.builtin_role_permissions(role, "Repository"))
    inherited = set(definitions[base]["permissions"])

    assert len(direct) == direct_count
    assert not direct & inherited
    assert direct | inherited == set(definitions[role]["permissions"])
    assert catalog.builtin_role_base(role, "Repository") == (base, "Repository")


@pytest.mark.parametrize("role,count", [("read", 4), ("write", 37), ("admin", 67)])
def test_no_extra_hierarchy_is_invented_for_roles_without_a_declared_base(role, count):
    result = catalog.builtin_role_permissions(role, "Repository")
    assert len(result["permissions_repository"]) == count
    assert catalog.builtin_role_base(role, "Repository") is None


@pytest.mark.parametrize("base", ["read", "triage", "write", "maintain", "admin"])
def test_all_repository_org_roles_keep_authority_on_cross_resource_inheritance(base):
    name = f"all_repo_{base}"
    result = catalog.builtin_role_permissions(name, "Organization")
    assert result is not None
    assert all(values == [] for values in result.values())
    assert catalog.builtin_role_base(name, "Organization") == (base, "Repository")


def test_security_manager_has_direct_repository_and_organization_actions():
    result = catalog.builtin_role_permissions("security_manager", "Organization")
    assert "manage_org_security_products" in result["permissions_organization"]
    assert "read_code_scanning" in result["permissions_repository"]
    assert "read_repo_contents" not in flattened(result)
    assert catalog.builtin_role_base("security_manager", "Organization") == (
        "read",
        "Repository",
    )


def test_business_resource_is_explicitly_mapped_to_enterprise_scope():
    expected = {
        "permissions_repository": [],
        "permissions_organization": [],
        "permissions_enterprise": ["manage_enterprise_security_products"],
        "permissions_unclassified": [],
    }
    assert (
        catalog.builtin_role_permissions("enterprise_security_manager", "Business")
        == expected
    )
    assert (
        catalog.builtin_role_permissions("enterprise_security_manager", "Enterprise")
        == expected
    )


@pytest.mark.parametrize(
    "name,target",
    [
        ("owners", "Organization"),
        ("owners", "Enterprise"),
        ("app_manager", "Organization"),
        ("moderate", "Repository"),
        ("all_repo_moderate", "Organization"),
        ("new_role", "Repository"),
        ("read", "Organization"),
        ("security_manager", "Enterprise"),
        ("codespace_org_creator", "Organization"),
    ],
)
def test_unknown_or_unresolved_baselines_remain_distinct_from_empty_direct_roles(
    name, target
):
    assert catalog.builtin_role_permissions(name, target) is None
    assert catalog.builtin_role_base(name, target) is None


def test_role_identity_includes_target_and_does_not_redirect_cross_resource_base(
    monkeypatch,
):
    roles = deepcopy(catalog._ROLES)
    roles[("Organization", "read")] = {
        "name": "read",
        "target_type": "Organization",
        "base": None,
        "base_target_type": None,
        "permissions": ["read_audit_logs"],
    }
    monkeypatch.setattr(catalog, "_ROLES", roles)
    assert catalog.builtin_role_permissions("read", "Organization")[
        "permissions_organization"
    ] == ["read_audit_logs"]
    assert catalog.builtin_role_base("security_manager", "Organization") == (
        "read",
        "Repository",
    )
    assert (
        "read_repo_contents"
        in catalog.builtin_role_permissions("read", "Repository")[
            "permissions_repository"
        ]
    )


@pytest.mark.parametrize("invalid", ["cycle", "missing", "unresolved"])
def test_invalid_base_chains_are_rejected_instead_of_silently_expanded(
    monkeypatch, invalid
):
    roles = deepcopy(catalog._ROLES)
    base = roles[("Repository", "write")]
    base["base"] = "maintain" if invalid == "cycle" else "missing"
    base["base_target_type"] = None if invalid == "unresolved" else "Repository"
    monkeypatch.setattr(catalog, "_ROLES", roles)
    with pytest.raises(ValueError, match="Cyclic|Missing or unresolved"):
        catalog.builtin_role_permissions("maintain", "Repository")


def test_api_declarations_are_not_mutated_or_merged_with_snapshot_baselines():
    current = ["edit_enterprise_package_firewall_policy"]
    differences = catalog.builtin_permission_differences(
        "enterprise_security_manager", "Enterprise", current
    )
    assert differences == {
        "catalog_only": ["manage_enterprise_security_products"],
        "collected_only": ["edit_enterprise_package_firewall_policy"],
    }
    assert current == ["edit_enterprise_package_firewall_policy"]
    assert catalog.split_role_permissions(current)["permissions_enterprise"] == current


def test_snapshot_lists_provenance_gaps_and_defines_every_declared_action():
    data = snapshot()
    assert len(data["metadata"]["source_sha256"]) == 64
    assert "app_manager" in data["metadata"]["known_missing_roles"]["Organization"]
    assert "owners" in data["metadata"]["known_missing_roles"]["Business"]
    declared = {p for r in data["system_roles"] for p in r["permissions"]}
    assert declared <= data["fine_grained_permissions"].keys()


def test_returned_lists_cannot_mutate_the_catalog_baseline():
    result = catalog.builtin_role_permissions("read", "Repository")
    result["permissions_repository"].append("made_up")
    assert "made_up" not in flattened(
        catalog.builtin_role_permissions("read", "Repository")
    )


def make_role(kind, **overrides):
    from datetime import datetime
    from unittest.mock import MagicMock

    from openhound_github.models.enterprise_role import EnterpriseRole
    from openhound_github.models.org_role import OrgRole
    from openhound_github.models.repository_role import RepoRole

    common = {"id": 42, "name": "custom", "permissions": []}
    if kind == "repository":
        cls = RepoRole
        extra = dict(
            type="custom",
            org_login="acme",
            repository_node_id="R_1",
            repository_name="repo",
            repository_full_name="acme/repo",
        )
    elif kind == "organization":
        cls = OrgRole
        extra = dict(
            type="custom",
            org_node_id="O_1",
            org_login="acme",
            created_at=datetime(2026, 1, 1),
        )
    else:
        cls = EnterpriseRole
        extra = dict(
            source="Enterprise", enterprise_node_id="E_1", enterprise_slug="acme"
        )
    role = cls(**(common | extra | overrides))
    role._lookup = configure_role_ids(MagicMock())
    role._lookup.enterprise_id.return_value = "E_1"
    return role


@pytest.mark.parametrize("kind", ["repository", "organization", "enterprise"])
def test_role_nodes_export_api_grants_by_target_without_changing_raw_data(kind):
    from dataclasses import asdict

    permissions = [
        "manage_org_security_products",
        "read_repo_contents",
        "manage_enterprise_security_products",
        "future_action",
        "read_repo_contents",
    ]
    role = make_role(kind, permissions=permissions, base_role="read")
    properties = asdict(role.as_node.properties)
    assert {k: v for k, v in properties.items() if k.startswith("permissions_")} == (
        catalog.split_role_permissions(permissions)
    )
    assert "permissions" not in properties
    assert properties["base_role"] == "read"
    assert role.permissions == permissions


@pytest.mark.parametrize(
    "name,base,count",
    [("triage", "read", 24), ("maintain", "write", 14), ("admin", None, 67)],
)
def test_synthesized_repository_node_exports_only_direct_catalog_permissions(
    name, base, count
):
    role = make_role("repository", name=name, type="default", base_role=base)
    properties = role.as_node.properties
    assert properties.base_role == base
    assert len(properties.permissions_repository) == count
    assert properties.permissions_organization == []
    assert properties.permissions_enterprise == []
    assert role.permissions == []  # Evaluators still receive the original data.
    if base:
        assert "read_repo_contents" not in properties.permissions_repository
        assert any(
            e.kind == "GH_HasBaseRole" and e.end.value == repo_role_id(base)
            for e in role.edges
        )


@pytest.mark.parametrize("kind", ["repository", "organization", "enterprise"])
def test_custom_role_named_like_builtin_does_not_receive_catalog_permissions(kind):
    role = make_role(kind, name="read")
    assert role.as_node.properties.permissions_repository == []
    assert role.as_node.properties.permissions_unclassified == []


@pytest.mark.parametrize("kind", ["organization", "enterprise"])
def test_predefined_api_empty_list_does_not_fall_back_to_catalog(kind):
    name = (
        "security_manager" if kind == "organization" else "enterprise_security_manager"
    )
    role = make_role(kind, name=name, source="Predefined")
    assert role.as_node.properties.permissions_repository == []
    assert role.as_node.properties.permissions_enterprise == []
    assert role.as_node.properties.permissions_unclassified == []


@pytest.mark.parametrize("kind", ["organization", "enterprise"])
@pytest.mark.parametrize("name", ["owners", "members"])
def test_missing_synthesized_baseline_exports_empty_properties(kind, name):
    role = make_role(kind, name=name, type="default", source="Default")
    properties = role.as_node.properties
    for scope in ["repository", "organization", "enterprise", "unclassified"]:
        assert getattr(properties, f"permissions_{scope}") == []


def test_predefined_api_disagreement_exports_only_current_api_permissions():
    role = make_role(
        "enterprise",
        name="enterprise_security_manager",
        source="Predefined",
        permissions=["edit_enterprise_package_firewall_policy"],
    )
    properties = role.as_node.properties
    assert properties.permissions_enterprise == [
        "edit_enterprise_package_firewall_policy"
    ]
    assert properties.permissions_unclassified == []
    assert "manage_enterprise_security_products" not in flattened(
        {key: getattr(properties, key) for key in catalog.split_role_permissions([])}
    )


def test_missing_api_list_is_distinct_from_explicit_empty_list():
    role = make_role("organization")
    role.__pydantic_fields_set__.discard("permissions")
    assert role.as_node.properties.permissions_organization is None
    assert make_role("organization").as_node.properties.permissions_organization == []


@pytest.mark.parametrize(
    "target,scope,permissions",
    [
        (
            "Organization",
            "organization",
            [
                "edit_custom_properties_for_organizations",
                "org_bypass_code_scanning_dismissal_requests",
                "org_bypass_dependabot_alert_dismissal_requests",
                "org_bypass_secret_scanning_closure_requests",
                "org_review_and_manage_secret_scanning_bypass_requests",
                "org_review_and_manage_secret_scanning_closure_requests",
                "read_custom_properties_for_organizations",
                "read_organization_network_configurations",
                "read_organization_runner_custom_images",
                "review_license_compliance_closure_requests",
                "review_org_code_scanning_dismissal_requests",
                "review_org_dependabot_alert_dismissal_requests",
                "view_license_compliance_closure_requests",
                "view_org_api_insights",
                "view_org_code_scanning_dismissal_requests",
                "view_org_dependabot_alert_dismissal_requests",
                "write_organization_network_configurations",
                "write_organization_runner_custom_images",
            ],
        ),
        (
            "Repository",
            "repository",
            [
                "publish_repository_advisories",
                "read_code_quality",
                "read_repository_advisories",
                "triage_repository_advisories",
                "view_repository_license_policy",
                "write_code_quality",
                "write_repository_advisories",
            ],
        ),
        (
            "Business",
            "enterprise",
            [
                "edit_enterprise_license_policy",
                "edit_enterprise_package_firewall_policy",
                "view_enterprise_license_policy",
            ],
        ),
    ],
)
def test_explicit_supplemental_permission_targets(target, scope, permissions):
    result = catalog.split_role_permissions(permissions)
    assert result[f"permissions_{scope}"] == sorted(permissions)
    assert result["permissions_unclassified"] == []
    assert sum(map(len, result.values())) == len(permissions)
    for permission in permissions:
        assert catalog.permission_target_type(permission) == target


@pytest.mark.parametrize(
    "kind,parent",
    [("repository", "R_1"), ("organization", "O_1"), ("enterprise", "E_1")],
)
@pytest.mark.parametrize("permissions", [[], ["future_permission"]])
def test_role_access_scope_always_identifies_its_exact_parent(
    kind, parent, permissions
):
    role = make_role(kind, permissions=permissions)
    role._lookup.repository_default_branch_collected.return_value = False
    role._lookup.role_can_create_branch.return_value = None
    edges = [e for e in role.edges if e.kind == "GH_CanAccess"]
    assert len(edges) == 1
    assert edges[0].start.value == role.node_id
    assert edges[0].end.value == parent
    assert edges[0].properties.traversable is False
    assert role.permissions == permissions
