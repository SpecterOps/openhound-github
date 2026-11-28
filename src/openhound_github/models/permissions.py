from typing import Any

from openhound_github.models.app_permissions import split_app_permissions


def normalize_permission_declaration(value: Any) -> list[str] | None:
    """Normalize GitHub permission payloads into query-friendly scope:access values."""
    if value is None:
        return None

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [str(item) for item in value]

    if isinstance(value, dict):
        return [f"{key!s}:{item!s}" for key, item in value.items()]

    return [str(value)]


def split_permission_groups(permissions: dict | None) -> dict[str, list[str]]:
    """Classify grouped PAT declarations using the same catalog as GitHub Apps."""
    result = split_app_permissions({})
    for group in (permissions or {}).values():
        for declaration in normalize_permission_declaration(group) or []:
            permission, separator, access = declaration.partition(":")
            classified = (
                split_app_permissions({permission: access})
                if separator
                else {"permissions_unclassified": [declaration]}
            )
            for field, values in classified.items():
                for value in values:
                    if value not in result[field]:
                        result[field].append(value)
    return result
