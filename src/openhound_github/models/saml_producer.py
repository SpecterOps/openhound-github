"""Settings and fact builders for the SAML nodes and edges this collector writes.

Every `SAML_*` node and edge comes from `openhound-saml-producer`. This module
only maps GitHub scope data to the library's facts. The service provider fact is
shared by the service provider asset and the external identity asset, so both
reach the same node ID and edge context.
"""

import logging
from collections.abc import Iterable

from openhound_saml_producer import (
    BuildWarning,
    IssuerFact,
    Producer,
    RouteFact,
    ServiceProviderFact,
)

from openhound_github.graph import SAML_SOURCE_KIND
from openhound_github.kinds import nodes as nk

from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    github_saml_route,
    normalize_scope_type,
)

logger = logging.getLogger(__name__)

# `github_` is the prefix for every collector-owned property on a SAML node or
# edge, so `github_deployment_id` and `github_web_origin` keep their names.
SAML = Producer(
    name="github_saml",
    extension="openhound-github",
    prefix="github_",
    technology="github",
    source_kind=SAML_SOURCE_KIND,
)


def service_provider_fact(
    *,
    saml_provider_id: str,
    environment_node_id: str,
    environment_name: str,
    environment_type: str,
    environment_slug: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> ServiceProviderFact:
    """Return the service provider fact for one GitHub organization or enterprise.

    The native key is the deployment, scope type, and slug, so a slug shared by
    github.com and a GHES deployment still gets two service providers. The native
    object is the `GH_SamlIdentityProvider` that implements the service provider.
    The fact has no extras: the service provider asset adds the node properties.
    """
    return ServiceProviderFact(
        environment_id=environment_node_id,
        native_key=f"{github_deployment_id.strip().lower()}:{environment_type}:{environment_slug}",
        native_kind=nk.SAML_IDENTITY_PROVIDER,
        native_object_id=saml_provider_id,
        name=environment_name,
        enabled=True,
    )


def issuer_fact(issuer: str | None, scope: str | None = None) -> IssuerFact | None:
    """Return the trusted issuer fact, or None when GitHub gave no usable issuer.

    A null, empty, or whitespace-only issuer names no issuer. So does an issuer
    with a line break, because the library rejects both and one bad row would
    stop the whole conversion. With a `scope`, a line break logs one warning.
    """
    if issuer is None or not (entity_id := issuer.strip()):
        return None
    if "\n" in entity_id or "\r" in entity_id:
        if scope:
            logger.warning(
                "Ignoring the SAML issuer of %s: it contains a line break", scope
            )
        return None
    return IssuerFact(entity_id=issuer)


def route_fact(
    environment_type: str, environment_slug: str, github_web_origin: str
) -> RouteFact:
    """Return the ACS route that GitHub derives from the scope and web origin."""
    acs_url, sp_entity_id = github_saml_route(
        environment_type, environment_slug, github_web_origin
    )
    return RouteFact(
        acs_url=acs_url,
        sp_entity_id=sp_entity_id,
        route_source=f"github_{normalize_scope_type(environment_type)}_scope_convention",
    )


def log_warnings(warnings: Iterable[BuildWarning]) -> None:
    """Log the library's build warnings. They are not graph output.

    Every account whose state GitHub does not report warns, so the level is debug.
    """
    for warning in warnings:
        logger.debug("%s", warning)
