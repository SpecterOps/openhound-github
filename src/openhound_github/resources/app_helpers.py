"""Schema compatibility for app resources shared by enterprise and organization collection."""

import logging
from urllib.parse import quote

import dlt
from dlt.extract.exceptions import CurrentSourceSchemaNotAvailable

from openhound_github.models.app_owner import OWNER_KINDS


logger = logging.getLogger(__name__)


def collect_app_owner(application, ctx, client):
    """Collect one identity per owner, without adding it to membership tables."""
    owner = application.owner
    if owner is None or owner.type not in OWNER_KINDS:
        return
    with ctx.cache_lock:
        if owner.node_id in ctx.emitted_app_owners:
            return
        ctx.emitted_app_owners.add(owner.node_id)

    record = owner.model_dump()
    endpoint = {"User": "users", "Organization": "orgs"}.get(owner.type)
    if endpoint is not None and client is not None:
        try:
            response = client.get(f"/{endpoint}/{quote(owner.login, safe='')}")
            response.raise_for_status()
            profile = response.json()
            if (
                profile.get("node_id") != owner.node_id
                or profile.get("type") != owner.type
            ):
                raise ValueError("Owner profile identity does not match App metadata")
            record.update(
                {
                    key: profile[key]
                    for key in ("name", "description", "company", "html_url")
                    if key in profile
                }
            )
        except Exception as exc:
            logger.warning("Using App metadata for owner '%s': %s", owner.login, exc)
    yield record


def migrate_app_context_schema() -> None:
    """Relax legacy organization-only columns without weakening data validation.

    DLT retains schema hints from earlier runs. Its discard-row contract prevents
    optional model fields from relaxing existing NOT NULL columns. Update only
    these known constraints before any app records reach normalization.
    """
    try:
        schema = dlt.current.source_schema()
    except CurrentSourceSchemaNotAvailable:
        # Resource functions can also be exercised directly outside a DLT source.
        return
    for table, names in (
        ("app_installations", ("org_login", "repository_selection")),
        ("applications", ("org_login",)),
    ):
        columns = schema.tables.get(table, {}).get("columns", {})
        for name in names:
            if name in columns:
                columns[name]["nullable"] = True
