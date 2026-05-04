from typing import Tuple

from dlt.extract.source import DltSource
from openhound.core.app import OpenHound
from openhound.core.collect import CollectContext
from openhound.core.preproc import PreProcContext

from .lookup import GithubLookup
from .transforms import transforms

app = OpenHound("github", source_kind="Github", help="OpenGraph collector for GitHub")


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

    Loads `organizations` and `repositories` tables so the converter can
    resolve cross-table references (org node IDs, repo visibility) without
    re-reading the full dataset.

    Run before convert:
        openhound preproc github <input_path> lookup.duckdb
    """
    return {
        "organizations": "organizations",
        "repositories": "repositories",
        "branch_protection_rules": "branch_protection_rules",
        "branch_push_allowances": "branch_push_allowances",
        "branch_pr_bypass_allowances": "branch_pr_bypass_allowances",
        "repo_role_assignments": "repo_role_assignments",
        "branches": "branches",
        "repo_roles": "repo_roles",
        "saml_provider": "saml_provider",
        "applications": "applications",
        "enterprise": "enterprise",
    }
