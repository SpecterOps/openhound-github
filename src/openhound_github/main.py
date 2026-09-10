from pathlib import Path
from typing import Tuple

from dlt.extract.source import DltSource
from openhound.core.app import OpenHound
from openhound.core.collect import CollectContext
from openhound.core.preproc import PreProcContext

from .lookup import GithubLookup
from .transforms import transforms

app = OpenHound("github", help="OpenGraph collector for GitHub")


def _reset_lookup_database(output_file: Path) -> None:
    """Remove derived lookup artifacts so each preprocess run starts clean."""
    output_file.unlink(missing_ok=True)
    Path(f"{output_file}.wal").unlink(missing_ok=True)


@app.collect()
def collect(ctx: CollectContext) -> DltSource:
    """Register a Typer CLI command that collects GitHub resources and stores them on disk.

    Args:
        ctx (CollectContext): DLT pipeline context with output path and pipeline configuration.
    """
    from openhound_github.source import source

    return source()


@app.convert(lookup=GithubLookup)
def convert(ctx: CollectContext) -> Tuple[DltSource, dict]:
    """Register a Typer CLI command that converts collected GitHub resources to OpenGraph nodes and edges.

    Args:
        ctx (CollectContext): Returns DLT pipeline context.

    Returns:
        Tuple[DltSource, dict]: A tuple containing the DLT source and a dictionary for extra shared properties
    """
    from openhound_github.source import source

    return source(), {}


@app.preproc(transformer=transforms)
def preproc(ctx: PreProcContext):
    """Build a DuckDB lookup database from collected data.

    Loads lookup tables so the converter can resolve cross-table references
    (org node IDs, repo visibility, workflow secrets/variables) without
    re-reading the full dataset.

    Run before convert:
        openhound preproc github <input_path> lookup.duckdb
    """
    _reset_lookup_database(ctx.pipeline.output_file)
    return {
        "organizations": "organizations",
        "repositories": "repositories",
        "repositories_graphql": "repositories_graphql",
        "branch_protection_rules": "branch_protection_rules",
        "branch_push_allowances": "branch_push_allowances",
        "branch_pr_bypass_allowances": "branch_pr_bypass_allowances",
        "repo_role_assignments": "repo_role_assignments",
        "branches": "branches",
        "repo_roles": "repo_roles",
        "users": "users",
        "teams": "teams",
        "team_external_groups": "team_external_groups",
        "team_members": "team_members",
        "saml_provider": "saml_provider",
        "external_identities": "external_identities",
        "applications": "applications",
        "enterprise": "enterprise",
        "enterprise_users": "enterprise_users",
        "enterprise_organizations": "enterprise_organizations",
        "enterprise_scim_groups": "enterprise_scim_groups",
        "enterprise_runner_groups": "enterprise_runner_groups",
        "enterprise_runner_group_organizations": "enterprise_runner_group_organizations",
        "enterprise_runner_group_memberships": "enterprise_runner_group_memberships",
        "enterprise_runners": "enterprise_runners",
        "runner_groups": "runner_groups",
        "org_runners": "org_runners",
        "org_runner_group_access": "org_runner_group_access",
        "org_runner_group_memberships": "org_runner_group_memberships",
        "repo_runners": "repo_runners",
        "org_roles": "org_roles",
        "org_role_members": "org_role_members",
        "org_role_teams": "org_role_teams",
        "projected_enterprise_teams": "projected_enterprise_teams",
        "environments": "environments",
        "environment_branch_policies": "environment_branch_policies",
        "environment_secrets": "environment_secrets",
        "environment_variables": "environment_variables",
        "organization_secrets": "organization_secrets",
        "organization_variables": "organization_variables",
        "repository_secrets": "repository_secrets",
        "repository_variables": "repository_variables",
        "selected_organization_secrets": "selected_organization_secrets",
        "selected_organization_variables": "selected_organization_variables",
        "workflow_jobs": "workflow_jobs",
        "workflow_steps": "workflow_steps",
        "workflows": "workflows",
    }
