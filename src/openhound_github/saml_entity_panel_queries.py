"""Producer-owned entity-panel queries for normalized SAML nodes."""

from __future__ import annotations

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk


ENTITY_PANEL_QUERY_VERSION = "saml-entity-panel-queries-v0.1.0"

_CYPHER_ESCAPES = {
    "\\": "\\\\",
    "'": "\\'",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def cypher_string_literal(value: str) -> str:
    """Encode a node ID as a deterministic Cypher string literal."""

    encoded: list[str] = []
    for character in value:
        if character in _CYPHER_ESCAPES:
            encoded.append(_CYPHER_ESCAPES[character])
        elif ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F:
            encoded.append(f"\\u{ord(character):04x}")
        else:
            encoded.append(character)
    return f"'{''.join(encoded)}'"


def node_entity_panel_queries(kind: str, node_id: str) -> dict[str, str]:
    """Return the canonical query properties for one normalized SAML node."""

    selected = cypher_string_literal(node_id.upper())
    if kind == nk.SAML_ISSUER:
        return {
            "query_federation_providers": (
                f"MATCH p=(:{nk.SAML_FEDERATION_PROVIDER})-[:{ek.SAML_ISSUES_AS}]->"
                f"(:{nk.SAML_ISSUER} {{objectid:{selected}}}) RETURN p"
            ),
            "query_service_providers": (
                f"MATCH p=(:{nk.SAML_SERVICE_PROVIDER})-[:{ek.SAML_TRUSTS_ISSUER}]->"
                f"(:{nk.SAML_ISSUER} {{objectid:{selected}}}) RETURN p"
            ),
        }
    if kind == nk.SAML_ASSERTION_CONSUMER_SERVICE:
        return {
            "query_federation_providers": (
                f"MATCH p=(:{nk.SAML_FEDERATION_PROVIDER})"
                f"-[:{ek.SAML_ISSUES_ASSERTIONS_TO}]->"
                f"(:{nk.SAML_ASSERTION_CONSUMER_SERVICE} "
                f"{{objectid:{selected}}}) RETURN p"
            ),
            "query_service_providers": (
                f"MATCH p=(:{nk.SAML_SERVICE_PROVIDER})"
                f"-[:{ek.SAML_HAS_ASSERTION_CONSUMER_SERVICE}]->"
                f"(:{nk.SAML_ASSERTION_CONSUMER_SERVICE} "
                f"{{objectid:{selected}}}) RETURN p"
            ),
        }
    raise ValueError(f"no entity-panel query profile for node kind {kind}")
