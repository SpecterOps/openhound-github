import duckdb


def ensure_optional_input_tables(
    con: duckdb.DuckDBPyConnection, schema: str = "github"
) -> None:
    """Create typed empty tables for zero-row derived-edge inputs.

    DLT omits resources that yield no rows. Enterprise GitHub App collection can
    legitimately have no branches, branch-protection rules, role assignments, or
    environment branch policies while the derived transforms still need stable
    input schemas.
    """
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.branches (
            id VARCHAR,
            name VARCHAR,
            branch_protection_rule JSON,
            repository_node_id VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.repositories_graphql (
            id VARCHAR,
            branch_ruleset_count BIGINT
        );
        CREATE TABLE IF NOT EXISTS {schema}.branch_protection_rules (
            id VARCHAR,
            repository_node_id VARCHAR,
            pattern VARCHAR,
            requires_approving_reviews BOOLEAN,
            lock_branch BOOLEAN,
            restricts_pushes BOOLEAN,
            is_admin_enforced BOOLEAN,
            bypass_pull_request_allowances JSON,
            push_allowances JSON,
            blocks_creations BOOLEAN
        );
        CREATE TABLE IF NOT EXISTS {schema}.repo_roles (
            id BIGINT,
            name VARCHAR,
            base_role VARCHAR,
            repository_node_id VARCHAR,
            permissions JSON
        );
        CREATE TABLE IF NOT EXISTS {schema}.repo_role_assignments (
            node_id VARCHAR,
            assignee_type VARCHAR,
            repo_node_id VARCHAR,
            role_name VARCHAR,
            base_role VARCHAR,
            role_permissions JSON
        );
        CREATE TABLE IF NOT EXISTS {schema}.users (
            id VARCHAR,
            role VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.teams (
            id VARCHAR,
            parent_team JSON
        );
        CREATE TABLE IF NOT EXISTS {schema}.team_members (
            team_id VARCHAR,
            id VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.org_role_members (
            node_id VARCHAR,
            org_role_name VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.org_role_teams (
            node_id VARCHAR,
            org_role_name VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.environment_branch_policies (
            environment_node_id VARCHAR,
            name VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.organization_variables (
            name VARCHAR,
            org_login VARCHAR,
            value VARCHAR,
            visibility VARCHAR,
            selected_repositories_url VARCHAR,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS {schema}.selected_organization_variables (
            org_login VARCHAR,
            variable_name VARCHAR,
            repository_node_id VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.enterprise_organizations (
            id VARCHAR,
            enterprise_node_id VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.enterprise_runner_groups (
            id BIGINT,
            name VARCHAR,
            visibility VARCHAR,
            enterprise_node_id VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.enterprise_runner_group_organizations (
            node_id VARCHAR,
            runner_group_id BIGINT,
            enterprise_node_id VARCHAR
        );
        CREATE TABLE IF NOT EXISTS {schema}.enterprise_runner_group_memberships (
            runner_group_id BIGINT,
            runner_id BIGINT,
            enterprise_node_id VARCHAR
        );
    """)
    con.execute(f"""
        ALTER TABLE {schema}.branches
            ADD COLUMN IF NOT EXISTS branch_protection_rule JSON;
        ALTER TABLE {schema}.branches
            ADD COLUMN IF NOT EXISTS name VARCHAR;

        ALTER TABLE {schema}.repositories_graphql
            ADD COLUMN IF NOT EXISTS id VARCHAR;
        ALTER TABLE {schema}.repositories_graphql
            ADD COLUMN IF NOT EXISTS branch_ruleset_count BIGINT;

        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS id VARCHAR;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS repository_node_id VARCHAR;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS pattern VARCHAR;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS requires_approving_reviews BOOLEAN;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS lock_branch BOOLEAN;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS restricts_pushes BOOLEAN;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS is_admin_enforced BOOLEAN;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS bypass_pull_request_allowances JSON;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS push_allowances JSON;
        ALTER TABLE {schema}.branch_protection_rules
            ADD COLUMN IF NOT EXISTS blocks_creations BOOLEAN;

        ALTER TABLE {schema}.repo_roles
            ADD COLUMN IF NOT EXISTS name VARCHAR;
        ALTER TABLE {schema}.repo_roles
            ADD COLUMN IF NOT EXISTS base_role VARCHAR;
        ALTER TABLE {schema}.repo_roles
            ADD COLUMN IF NOT EXISTS permissions JSON;

        ALTER TABLE {schema}.repo_role_assignments
            ADD COLUMN IF NOT EXISTS node_id VARCHAR;
        ALTER TABLE {schema}.repo_role_assignments
            ADD COLUMN IF NOT EXISTS assignee_type VARCHAR;
        ALTER TABLE {schema}.repo_role_assignments
            ADD COLUMN IF NOT EXISTS repo_node_id VARCHAR;
        ALTER TABLE {schema}.repo_role_assignments
            ADD COLUMN IF NOT EXISTS role_name VARCHAR;
        ALTER TABLE {schema}.repo_role_assignments
            ADD COLUMN IF NOT EXISTS base_role VARCHAR;
        ALTER TABLE {schema}.repo_role_assignments
            ADD COLUMN IF NOT EXISTS role_permissions JSON;

        ALTER TABLE {schema}.users
            ADD COLUMN IF NOT EXISTS id VARCHAR;
        ALTER TABLE {schema}.users
            ADD COLUMN IF NOT EXISTS role VARCHAR;
        ALTER TABLE {schema}.users
            ADD COLUMN IF NOT EXISTS org_login VARCHAR;

        ALTER TABLE {schema}.teams
            ADD COLUMN IF NOT EXISTS id VARCHAR;
        ALTER TABLE {schema}.teams
            ADD COLUMN IF NOT EXISTS parent_team JSON;

        ALTER TABLE {schema}.team_members
            ADD COLUMN IF NOT EXISTS team_id VARCHAR;
        ALTER TABLE {schema}.team_members
            ADD COLUMN IF NOT EXISTS id VARCHAR;

        ALTER TABLE {schema}.org_role_members
            ADD COLUMN IF NOT EXISTS node_id VARCHAR;
        ALTER TABLE {schema}.org_role_members
            ADD COLUMN IF NOT EXISTS org_role_name VARCHAR;
        ALTER TABLE {schema}.org_role_members
            ADD COLUMN IF NOT EXISTS org_login VARCHAR;

        ALTER TABLE {schema}.org_role_teams
            ADD COLUMN IF NOT EXISTS node_id VARCHAR;
        ALTER TABLE {schema}.org_role_teams
            ADD COLUMN IF NOT EXISTS org_role_name VARCHAR;
        ALTER TABLE {schema}.org_role_teams
            ADD COLUMN IF NOT EXISTS org_login VARCHAR;

        ALTER TABLE {schema}.environment_branch_policies
            ADD COLUMN IF NOT EXISTS environment_node_id VARCHAR;
        ALTER TABLE {schema}.environment_branch_policies
            ADD COLUMN IF NOT EXISTS name VARCHAR;

        ALTER TABLE {schema}.organization_variables
            ADD COLUMN IF NOT EXISTS name VARCHAR;
        ALTER TABLE {schema}.organization_variables
            ADD COLUMN IF NOT EXISTS org_login VARCHAR;

        ALTER TABLE {schema}.selected_organization_variables
            ADD COLUMN IF NOT EXISTS org_login VARCHAR;
        ALTER TABLE {schema}.selected_organization_variables
            ADD COLUMN IF NOT EXISTS variable_name VARCHAR;
        ALTER TABLE {schema}.selected_organization_variables
            ADD COLUMN IF NOT EXISTS repository_node_id VARCHAR;

        ALTER TABLE {schema}.enterprise_organizations
            ADD COLUMN IF NOT EXISTS id VARCHAR;
        ALTER TABLE {schema}.enterprise_organizations
            ADD COLUMN IF NOT EXISTS enterprise_node_id VARCHAR;

        ALTER TABLE {schema}.enterprise_runner_groups
            ADD COLUMN IF NOT EXISTS id BIGINT;
        ALTER TABLE {schema}.enterprise_runner_groups
            ADD COLUMN IF NOT EXISTS name VARCHAR;
        ALTER TABLE {schema}.enterprise_runner_groups
            ADD COLUMN IF NOT EXISTS visibility VARCHAR;
        ALTER TABLE {schema}.enterprise_runner_groups
            ADD COLUMN IF NOT EXISTS enterprise_node_id VARCHAR;

        ALTER TABLE {schema}.enterprise_runner_group_organizations
            ADD COLUMN IF NOT EXISTS node_id VARCHAR;
        ALTER TABLE {schema}.enterprise_runner_group_organizations
            ADD COLUMN IF NOT EXISTS runner_group_id BIGINT;
        ALTER TABLE {schema}.enterprise_runner_group_organizations
            ADD COLUMN IF NOT EXISTS enterprise_node_id VARCHAR;

        ALTER TABLE {schema}.enterprise_runner_group_memberships
            ADD COLUMN IF NOT EXISTS runner_group_id BIGINT;
        ALTER TABLE {schema}.enterprise_runner_group_memberships
            ADD COLUMN IF NOT EXISTS runner_id BIGINT;
        ALTER TABLE {schema}.enterprise_runner_group_memberships
            ADD COLUMN IF NOT EXISTS enterprise_node_id VARCHAR;
    """)

# TODO:
# This can be optimized to generate the actor_branch_gates table
# in one go instead of intermedaite tables
def join_branch_bpr(con, schema: str = "github"):
    con.execute(f"""
        CREATE OR REPLACE TABLE {schema}.branch_bpr AS
        SELECT b.*, r.*
        FROM {schema}.branches b
        JOIN {schema}.branch_protection_rules r
        ON r.id = json_extract_string(b.branch_protection_rule, '$.id');
    """)


def actor_allowances(con, schema: str = "github"):
    con.execute(f"""
        CREATE OR REPLACE TABLE {schema}.actor_branch_bypass AS
        SELECT
            id as branch_id,
            id_1 as rule_id,
            repository_node_id,
            'bypass_pull_request_allowances' AS bypass_type,
            bypass_node->>'$.actor.id'       AS actor_id
        FROM {schema}.branch_bpr,
            UNNEST(json_extract(bypass_pull_request_allowances, '$.nodes')::JSON[]) AS t(bypass_node)

        UNION ALL

        SELECT
            id as branch_id,
            id_1 as rule_id,
            repository_node_id,
            'push_allowances'          AS bypass_type,
            push_node->>'$.actor.id'   AS actor_id
        FROM {schema}.branch_bpr,
            UNNEST(json_extract(push_allowances, '$.nodes')::JSON[]) AS t(push_node)
    """)


def role_can_create_branch(con, schema: str = "github"):
    con.execute(f"""
        CREATE OR REPLACE TABLE {schema}.role_can_create_branch AS
        SELECT DISTINCT rr.id, rr.repository_node_id
        FROM {schema}.repo_roles rr
        WHERE NOT EXISTS (
            SELECT 1
            FROM {schema}.branch_protection_rules bpr
            WHERE bpr.repository_node_id = rr.repository_node_id
            AND bpr.pattern           = '*'
            AND bpr.blocks_creations  = true
            AND NOT (
                bpr.is_admin_enforced = false
                AND json_contains(rr.permissions, '"push_protected_branch"')
            )
        )""")


def unprotected_branches(con, schema: str = "github"):
    con.execute(f"""
        CREATE OR REPLACE TABLE {schema}.unprotected_branches AS
            SELECT * FROM {schema}.branches
            WHERE branch_protection_rule IS NULL
                OR id IN (SELECT id FROM {schema}.branch_bpr WHERE requires_approving_reviews = false AND lock_branch = false AND restricts_pushes = false);
    """)


def actor_branch_gates(con, schema: str = "github"):
    """Generate a table to check for actor-based allownaces"""
    con.execute(f"""
        CREATE OR REPLACE TABLE {schema}.actor_branch_gates AS
        SELECT
            ab.actor_id,
            ab.branch_id,
            ab.repository_node_id,
            BOOL_OR(ab.bypass_type = 'push_allowances') AS has_push_allowance,
            BOOL_OR(ab.bypass_type = 'bypass_pull_request_allowances') AS has_pr_allowance,
            ANY_VALUE(b.requires_approving_reviews) AS requires_approving_reviews,
            ANY_VALUE(b.lock_branch) AS lock_branch,
            ANY_VALUE(b.restricts_pushes) AS restricts_pushes,
            ANY_VALUE(b.is_admin_enforced) AS is_admin_enforced
        FROM {schema}.actor_branch_bypass ab
        JOIN {schema}.branch_bpr b ON ab.branch_id = b.id
        GROUP BY ab.actor_id, ab.branch_id, ab.repository_node_id
    """)


def transforms(con: duckdb.DuckDBPyConnection, schema: str = "github") -> None:
    """Apply all preprocessing transformations to the DuckDB lookup database.

    Args:
        con: The DuckDB connection to use for creating computed tables.
        schema: The DuckDB schema name containing the source tables.
    """

    ensure_optional_input_tables(con, schema)
    join_branch_bpr(con, schema)
    actor_allowances(con, schema)
    unprotected_branches(con, schema)
    actor_branch_gates(con, schema)
    role_can_create_branch(con, schema)
