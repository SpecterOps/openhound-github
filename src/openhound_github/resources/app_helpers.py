"""Schema compatibility for app resources shared by enterprise and organization collection."""

import dlt
from dlt.extract.exceptions import CurrentSourceSchemaNotAvailable


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
