"""Preparatory native-role catalog; existing evaluators do not use these helpers.

The packaged snapshot retains the user-supplied declarations and their provenance.
Role permissions are action identifiers, not App-style permission:access pairs.
Catalog baselines are separate from current API observations. Callers must verify
that a role is predefined before using a built-in baseline for a collected role.
"""

from collections.abc import Iterable
from importlib.resources import files
import json


_CATALOG = json.loads(
    files("openhound_github").joinpath("data/role_permissions.json").read_text()
)
_ROLES = {
    (role["target_type"], role["name"]): role for role in _CATALOG["system_roles"]
}
_PERMISSIONS = {
    **_CATALOG["fine_grained_permissions"],
    **_CATALOG["supplemental_permission_targets"],
}
_SCOPE_FOR_TARGET = {
    "Repository": "repository",
    "Organization": "organization",
    "Business": "enterprise",
}


def permission_target_type(permission: str) -> str | None:
    """Return the declared resource type without guessing from an action's name."""
    return _PERMISSIONS.get(permission, {}).get("target_type")


def split_role_permissions(permissions: Iterable[str]) -> dict[str, list[str]]:
    """Preserve native names; unknown or unsupported targets remain unclassified."""
    result = {
        f"permissions_{scope}": []
        for scope in (*_SCOPE_FOR_TARGET.values(), "unclassified")
    }
    for permission in sorted(set(permissions)):
        scope = _SCOPE_FOR_TARGET.get(
            permission_target_type(permission), "unclassified"
        )
        result[f"permissions_{scope}"].append(permission)
    return result


def _base_role(role_key: tuple[str, str]) -> tuple[str, str] | None:
    role = _ROLES[role_key]
    base = role["base"]
    if base is None:
        return None
    base_key = (role["base_target_type"], base)
    if base_key[0] is None or base_key not in _ROLES:
        raise ValueError(
            f"Missing or unresolved base role definition for {role_key}: {base_key}"
        )
    return base_key


def _effective_permissions(
    role_key: tuple[str, str], ancestry: tuple[tuple[str, str], ...] = ()
) -> set[str]:
    if role_key in ancestry:
        raise ValueError(f"Cyclic role catalog inheritance: {(*ancestry, role_key)}")
    role = _ROLES[role_key]
    permissions = set(role["permissions"])
    base = _base_role(role_key)
    if base is not None:
        permissions |= _effective_permissions(base, (*ancestry, role_key))
    return permissions


def builtin_role_permissions(
    role_name: str, target_type: str
) -> dict[str, list[str]] | None:
    """Return direct snapshot permissions, or None for an unresolved baseline.

    Subtract the complete declared base chain, leaving inheritance to the role
    structure. Explicit baseline entries are retained when no base is declared.
    Business is GitHub's source name for the enterprise resource type.
    """
    target_type = "Business" if target_type == "Enterprise" else target_type
    role_key = (target_type, role_name)
    role = _ROLES.get(role_key)
    if (
        role is None
        or role["target_type"] is None
        or role["target_type"] != target_type
    ):
        return None
    # Validate the complete chain even when the role has no direct declarations.
    _effective_permissions(role_key)
    direct = set(role["permissions"])
    base = _base_role(role_key)
    if base is not None:
        direct -= _effective_permissions(base)
    return split_role_permissions(direct)


def builtin_role_base(role_name: str, target_type: str) -> tuple[str, str] | None:
    """Describe a known base role, including cross-resource inheritance."""
    if builtin_role_permissions(role_name, target_type) is None:
        return None
    target_type = "Business" if target_type == "Enterprise" else target_type
    base = _base_role((target_type, role_name))
    if base is None:
        return None
    return base[1], base[0]


def builtin_permission_differences(
    role_name: str, target_type: str, collected_permissions: Iterable[str]
) -> dict[str, list[str]] | None:
    """Report snapshot differences for review, without merging API declarations."""
    baseline = builtin_role_permissions(role_name, target_type)
    if baseline is None:
        return None
    expected = {permission for group in baseline.values() for permission in group}
    collected = set(collected_permissions)
    base = builtin_role_base(role_name, target_type)
    if base is not None:
        collected -= _effective_permissions((base[1], base[0]))
    return {
        "catalog_only": sorted(expected - collected),
        "collected_only": sorted(collected - expected),
    }


def role_permission_properties(
    role_name: str,
    target_type: str,
    permissions: Iterable[str] | None,
    *,
    synthesized: bool,
) -> dict[str, list[str] | None]:
    """Export direct API grants or a verified synthesized-role baseline.

    API lists, including empty lists, remain authoritative. Synthesized records
    carry empty placeholder lists; only those use the packaged catalog. Missing
    synthesized baselines export empty arrays pending definitions; catalog
    metadata continues to track the missing baselines.
    """
    if synthesized:
        baseline = builtin_role_permissions(role_name, target_type)
        return baseline if baseline is not None else split_role_permissions([])
    elif permissions is not None:
        return split_role_permissions(permissions)
    return {key: None for key in split_role_permissions([])}
