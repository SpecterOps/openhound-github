"""Explicit role-ID stubs for tests that mock the collection lookup."""

from openhound_github.role_ids import role_node_id


def org_role_id(name, role_id=1):
    builtin = name in {"owners", "members"}
    return role_node_id(
        "organization", 1, name if builtin else role_id, builtin=builtin
    )


def repo_role_id(name, role_id=1):
    builtin = name in {"read", "triage", "write", "maintain", "admin"}
    return role_node_id("repository", 1, name if builtin else role_id, builtin=builtin)


def configure_role_ids(lookup):
    lookup.role_parent_database_id.return_value = 1
    lookup.org_role_node_id.side_effect = lambda parent, name: org_role_id(name)
    lookup.repo_role_node_id.side_effect = lambda parent, name: repo_role_id(name)
    lookup.enterprise_role_node_id.side_effect = lambda parent, key: role_node_id(
        "enterprise",
        1,
        key if key in {"owners", "members"} else int(key),
        builtin=key in {"owners", "members"},
    )
    return lookup
