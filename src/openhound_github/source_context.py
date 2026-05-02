from dataclasses import dataclass
from typing import Iterator

from dlt.sources.helpers.rest_client.client import RESTClient


@dataclass
class OrgContext:
    """Immutable per-organization collection context."""

    client: RESTClient
    org_name: str
    org_node_id: str | None = None


@dataclass
class SourceContext:
    """Shared context for GitHub API access."""

    client: RESTClient
    org_name: str | None = None
    org_node_id: str | None = None
    org_contexts: tuple[OrgContext, ...] = ()
    enterprise_name: str | None = None
    enterprise_node_id: str | None = None
    enterprise_saml_enabled: bool = False
    auth_type: str | None = None


def _with_org_context(ctx: SourceContext, org_ctx: OrgContext) -> SourceContext:
    return SourceContext(
        client=org_ctx.client,
        org_name=org_ctx.org_name,
        org_node_id=org_ctx.org_node_id,
        enterprise_name=ctx.enterprise_name,
        enterprise_node_id=ctx.enterprise_node_id,
        enterprise_saml_enabled=ctx.enterprise_saml_enabled,
        auth_type=ctx.auth_type,
    )


def _iter_collection_contexts(ctx: SourceContext) -> Iterator[SourceContext]:
    if ctx.org_contexts:
        for org_ctx in ctx.org_contexts:
            yield _with_org_context(ctx, org_ctx)
    elif ctx.org_name:
        yield ctx


def _org_context_for(
    ctx: SourceContext, org_login: str | None, org_node_id: str | None = None
) -> SourceContext:
    for org_ctx in ctx.org_contexts:
        if org_login and org_ctx.org_name == org_login:
            return _with_org_context(ctx, org_ctx)
        if org_node_id and org_ctx.org_node_id == org_node_id:
            return _with_org_context(ctx, org_ctx)
    return SourceContext(
        client=ctx.client,
        org_name=org_login or ctx.org_name,
        org_node_id=org_node_id or ctx.org_node_id,
        enterprise_name=ctx.enterprise_name,
        enterprise_node_id=ctx.enterprise_node_id,
        enterprise_saml_enabled=ctx.enterprise_saml_enabled,
        auth_type=ctx.auth_type,
    )
