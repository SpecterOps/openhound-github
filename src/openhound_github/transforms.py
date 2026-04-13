import duckdb


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
    # TODO: Double check json_contains vs '' IN
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
                AND json_contains(rr.permissions, 'push_protected_branch')
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
    join_branch_bpr(con, schema)
    actor_allowances(con, schema)
    role_can_create_branch(con, schema)
    unprotected_branches(con, schema)
    actor_branch_gates(con, schema)
