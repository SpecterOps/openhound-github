"""Recover branch-protection actor fields when GraphQL returns partial errors."""

import logging
from urllib.parse import quote

from dlt.sources.helpers.rest_client.client import RESTClient

logger = logging.getLogger(__name__)

ALLOWANCE_FIELDS = frozenset({"pushAllowances", "bypassPullRequestAllowances"})


def _rest_actors(payload: dict, field: str) -> list[dict]:
    if field == "pushAllowances":
        allowance = payload.get("restrictions")
    else:
        reviews = payload.get("required_pull_request_reviews") or {}
        allowance = reviews.get("bypass_pull_request_allowances")
    if not isinstance(allowance, dict):
        raise ValueError("REST response omitted the affected allowance")

    nodes = []
    for key, actor_type, name_key in (
        ("users", "User", "login"),
        ("teams", "Team", "slug"),
        ("apps", "App", "slug"),
    ):
        actors = allowance.get(key)
        if not isinstance(actors, list):
            raise ValueError(f"REST response omitted the {key} list")
        for actor in actors:
            if not isinstance(actor, dict) or not actor.get("node_id"):
                raise ValueError(f"REST {key} entry has no node ID")
            nodes.append(
                {
                    "actor": {
                        "__typename": actor_type,
                        "id": actor["node_id"],
                        name_key: actor.get(name_key),
                    }
                }
            )
    return nodes


def _merge_actors(graphql_nodes: list[dict], rest_nodes: list[dict]) -> list[dict]:
    """Prefer GraphQL identities; handles also deduplicate differing ID formats."""
    merged = []
    ids = set()
    names = set()
    for node in [*graphql_nodes, *rest_nodes]:
        actor = node.get("actor") if node else None
        if not actor:
            continue
        actor_id = actor.get("id")
        actor_type = actor.get("__typename") or actor.get("typename")
        name = actor.get("slug") or actor.get("login")
        name_key = (actor_type, name.casefold()) if actor_type and name else None
        if (actor_id and actor_id in ids) or (name_key and name_key in names):
            continue
        merged.append(node)
        if actor_id:
            ids.add(actor_id)
        if name_key:
            names.add(name_key)
    return merged


def recover_branch_allowances(
    rule: dict,
    fields: set[str],
    client: RESTClient,
    org_login: str,
    repository_name: str,
    branch_name: str | None,
) -> dict:
    """Use one REST request per affected rule, retaining successful GraphQL actors."""
    try:
        if not branch_name:
            raise ValueError("no representative branch was collected for this rule")
        path = "/repos/{}/{}/branches/{}/protection".format(
            quote(org_login, safe=""),
            quote(repository_name, safe=""),
            quote(branch_name, safe=""),
        )
        response = client.get(path)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid REST branch protection response")
    except Exception as exc:
        logger.warning(
            "Branch protection allowance collection gap for '%s/%s', rule '%s', "
            "fields %s: GraphQL failed and REST recovery failed: %s",
            org_login,
            repository_name,
            rule.get("id"),
            sorted(fields),
            exc,
        )
        return rule

    rule = dict(rule)
    for field in sorted(fields):
        try:
            rest_nodes = _rest_actors(payload, field)
            original = rule.get(field) or {}
            rule[field] = {
                **original,
                "nodes": _merge_actors(original.get("nodes") or [], rest_nodes),
            }
            logger.info(
                "Recovered '%s' via REST for '%s/%s', rule '%s' after GraphQL errors",
                field,
                org_login,
                repository_name,
                rule.get("id"),
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Branch protection allowance collection gap for '%s/%s', rule '%s', "
                "field '%s': REST recovery incomplete: %s",
                org_login,
                repository_name,
                rule.get("id"),
                field,
                exc,
            )
    return rule
