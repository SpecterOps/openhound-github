from typing import Any


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
