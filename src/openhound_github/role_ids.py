"""Versioned collector role identities; these are not native GitHub node IDs."""

import base64

import msgpack


ROLE_PREFIXES = {"repository": "GH_RR", "organization": "GH_OR", "enterprise": "GH_ER"}


def role_node_id(
    kind: str, parent_database_id: int, role_key: str | int, *, builtin: bool
) -> str:
    """Scope API role IDs and synthesized stable keys to their parent resource."""
    if kind not in ROLE_PREFIXES:
        raise ValueError(f"Unsupported role kind: {kind}")
    if type(parent_database_id) is not int or parent_database_id <= 0:
        raise ValueError("A positive parent database ID is required for role IDs")
    if builtin:
        if not isinstance(role_key, str) or not role_key.strip():
            raise ValueError("A nonempty stable key is required for built-in roles")
    elif type(role_key) is not int or role_key <= 0:
        raise ValueError("A positive numeric GitHub role ID is required for API roles")
    payload = msgpack.packb(
        [1, parent_database_id, "builtin" if builtin else "api", role_key],
        use_bin_type=True,
    )
    return (
        ROLE_PREFIXES[kind]
        + "_"
        + base64.urlsafe_b64encode(payload).decode().rstrip("=")
    )
