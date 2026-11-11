"""Observed native ET_ encoding; prefer IDs returned by GitHub when available.

Organization REST lists encode [0, enterprise database ID, team database ID] in
MessagePack. This fallback is observed behavior, not a documented API contract.
"""

import base64
import struct


def _uint(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("GitHub database ID must be an unsigned 64-bit integer")
    return (
        struct.pack(">BI", 0xCE, value)
        if value <= 0xFFFFFFFF
        else struct.pack(">BQ", 0xCF, value)
    )


def enterprise_database_id(node_id: str) -> int:
    if not node_id.startswith("E_"):
        raise ValueError(
            "Cannot derive enterprise-team ID from an unrecognized enterprise node ID"
        )
    encoded = node_id[2:]
    try:
        payload = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True
        )
    except ValueError as exc:
        raise ValueError("Invalid enterprise node ID encoding") from exc
    if len(payload) == 7 and payload[:3] == b"\x92\x00\xce":
        return struct.unpack(">I", payload[3:])[0]
    if len(payload) == 11 and payload[:3] == b"\x92\x00\xcf":
        return struct.unpack(">Q", payload[3:])[0]
    raise ValueError("Unrecognized enterprise node ID payload")


def enterprise_team_node_id(enterprise_id: str, team_id: str | int) -> str:
    payload = (
        b"\x93\x00" + _uint(enterprise_database_id(enterprise_id)) + _uint(int(team_id))
    )
    return "ET_" + base64.urlsafe_b64encode(payload).decode().rstrip("=")
