"""Collector-owned, versioned identities for fine-grained PATs and requests."""

from base64 import urlsafe_b64encode

import logging

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


def collected_pat_node_id(
    organization_id: int | None,
    credential_id: int,
    *,
    org_login: str,
    resource: str,
    request: bool = False,
) -> str | None:
    """Skip unidentifiable collected objects without inventing organization IDs."""
    if type(organization_id) is not int or not 0 < organization_id < 2**64:
        logging.getLogger(__name__).warning(
            "Skipping %s record %s for organization %r: missing or invalid organization database ID",
            resource,
            credential_id,
            org_login,
            extra={
                "resource": resource,
                "phase": "conversion",
                "org_login": org_login,
                "credential_id": credential_id,
            },
        )
        return None
    factory = pat_request_node_id if request else pat_node_id
    return factory(organization_id, credential_id)
