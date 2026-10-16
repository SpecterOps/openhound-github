from typing import Any

from pydantic import BaseModel


class EnterpriseCredentialInventory(BaseModel):
    """A downloaded credential export, before credential-specific parsing.

    Keep CSV fields as raw values so unknown credential types and new columns
    survive collection. DLT returns dictionaries for the downstream parser.
    """

    export_id: str
    as_of: str | None = None
    created_with_fallback: bool
    columns: list[str]
    rows: list[dict[str, Any]]
    enterprise_node_id: str
    enterprise_name: str
