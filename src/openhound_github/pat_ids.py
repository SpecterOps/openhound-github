"""Collector-owned, versioned identities for fine-grained PATs and requests."""

from base64 import urlsafe_b64encode

import msgpack


def _node_id(prefix: str, organization_id: int, database_id: int) -> str:
    for label, value in (
        ("organization", organization_id),
        ("credential", database_id),
    ):
        if type(value) is not int or not 0 < value < 2**64:
            raise ValueError(f"Missing or invalid {label} database ID: {value!r}")
    payload = msgpack.packb([1, organization_id, database_id])
    return prefix + "_" + urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def pat_node_id(organization_id: int, grant_id: int) -> str:
    return _node_id("PAT", organization_id, grant_id)


def pat_request_node_id(organization_id: int, request_id: int) -> str:
    return _node_id("PATR", organization_id, request_id)
