import json
from functools import lru_cache

import duckdb
from duckdb import DuckDBPyConnection
from openhound.core.lookup import LookupManager, logger

from openhound_github.runner_ids import runner_group_node_id, runner_node_id


class GithubLookup(LookupManager):
    def __init__(self, client: DuckDBPyConnection, schema: str = "github"):
        super().__init__(client, schema)
        self.schema = schema
        self.client = client

    def _find_single_row(self, *args):
        try:
            self.client.execute(*args)
            result = self.client.fetchone()
            return result if result else None

        except duckdb.CatalogException as err:
            logger.error("DuckDB lookup failed, missing table: %s", err)
            return None

        except duckdb.Error as err:
            logger.error("DuckDB lookup query failed: %s", err)
            return None

    @lru_cache
    def org_id(self) -> str | None:
        res = self._find_single_object(
            f"""SELECT node_id FROM {self.schema}.organizations"""
        )
        return res

    @lru_cache
    def org_id_for_login(self, org_login: str) -> str | None:
        return self._find_single_object(
            f"""SELECT node_id FROM {self.schema}.organizations WHERE login = ?""",
            [org_login],
        )

    @lru_cache
    def org_login(self) -> str | None:
        res = self._find_single_object(
            f"""SELECT login FROM {self.schema}.organizations"""
        )
        return res

    @lru_cache
    def enterprise_id(self) -> str | None:
        res = self._find_single_object(f"""SELECT id FROM {self.schema}.enterprise""")
        return res

    @lru_cache
    def enterprise_organization_node_ids(self, enterprise_node_id: str):
        return self._find_all_objects(
            f"""SELECT id FROM {self.schema}.enterprise_organizations WHERE enterprise_node_id = ?""",
            [enterprise_node_id],
        )

    @lru_cache
    def _enterprise_runner_group_identity_for_inherited_org_group(
        self, org_node_id: str, group_name: str
    ) -> tuple[str, int] | None:
        rows = self._find_all_objects(
            f"""
            WITH candidate_groups AS (
                SELECT erg.enterprise_node_id, erg.id
                FROM {self.schema}.enterprise_runner_groups erg
                JOIN {self.schema}.enterprise_organizations eo
                  ON eo.enterprise_node_id = erg.enterprise_node_id
                WHERE eo.id = ?
                  AND erg.visibility = 'all'
                  AND erg.name = ?

                UNION

                SELECT erg.enterprise_node_id, erg.id
                FROM {self.schema}.enterprise_runner_groups erg
                JOIN {self.schema}.enterprise_runner_group_organizations ergo
                  ON ergo.enterprise_node_id = erg.enterprise_node_id
                 AND ergo.runner_group_id = erg.id
                WHERE ergo.node_id = ?
                  AND erg.name = ?
            )
            SELECT enterprise_node_id, id
            FROM candidate_groups
            """,
            [org_node_id, group_name, org_node_id, group_name],
        )
        if not rows or len(rows) != 1:
            return None

        enterprise_node_id, runner_group_id = rows[0]
        return str(enterprise_node_id), int(runner_group_id)

    @lru_cache
    def enterprise_runner_group_node_id_for_inherited_org_group(
        self, org_node_id: str, group_name: str
    ) -> str | None:
        identity = self._enterprise_runner_group_identity_for_inherited_org_group(
            org_node_id, group_name
        )
        if not identity:
            return None

        enterprise_node_id, runner_group_id = identity
        return runner_group_node_id(enterprise_node_id, runner_group_id)

    @lru_cache
    def enterprise_runner_group_restricted_to_workflows_for_inherited_org_group(
        self, org_node_id: str, group_name: str
    ) -> bool | None:
        identity = self._enterprise_runner_group_identity_for_inherited_org_group(
            org_node_id, group_name
        )
        if not identity:
            return None

        enterprise_node_id, runner_group_id = identity
        row = self._find_single_row(
            f"""
            SELECT restricted_to_workflows
            FROM {self.schema}.enterprise_runner_groups
            WHERE enterprise_node_id = ?
              AND id = ?
            """,
            [enterprise_node_id, runner_group_id],
        )
        if row is None or row[0] is None:
            return None
        return bool(row[0])

    @lru_cache
    def enterprise_runner_node_ids_for_inherited_org_group(
        self, org_node_id: str, group_name: str
    ):
        identity = self._enterprise_runner_group_identity_for_inherited_org_group(
            org_node_id, group_name
        )
        if not identity:
            return []

        enterprise_node_id, runner_group_id = identity
        rows = self._find_all_objects(
            f"""
            SELECT runner_id
            FROM {self.schema}.enterprise_runner_group_memberships
            WHERE enterprise_node_id = ?
              AND runner_group_id = ?
            """,
            [enterprise_node_id, runner_group_id],
        )
        return [(runner_node_id(enterprise_node_id, int(runner_id)),) for (runner_id,) in rows]

    @lru_cache
    def enterprise_idp_for_scope(
        self, enterprise_node_id: str
    ) -> tuple[str | None, str | None] | None:
        return self._find_single_row(
            f"""SELECT issuer, sso_url
            FROM {self.schema}.saml_provider
            WHERE environment_node_id = ? AND environment_type = 'enterprise'
            LIMIT 1""",
            [enterprise_node_id],
        )

    @lru_cache
    def warn_missing_legacy_scim_okta_tenant_once(
        self, enterprise_node_id: str, enterprise_name: str
    ) -> None:
        logger.warning(
            "Legacy SCIM correlations are enabled for GitHub enterprise '%s' "
            "(%s), but no Okta tenant could be derived from its SAML provider; "
            "skipping IdP-to-SCIM group edges.",
            enterprise_name,
            enterprise_node_id,
        )

    @lru_cache
    def org_login_for_id(self, org_node_id: str) -> str | None:
        return self._find_single_object(
            f"""SELECT login FROM {self.schema}.organizations WHERE node_id = ?""",
            [org_node_id],
        )

    @lru_cache
    def projected_enterprise_team_exists(self, org_login: str, slug: str):
        return self._find_single_object(
            f"""SELECT slug FROM {self.schema}.projected_enterprise_teams WHERE org_login = ? AND slug = ?""",
            [org_login, slug],
        )

    @lru_cache
    def repository_node_ids(self):
        return self._find_all_objects(
            f"""SELECT node_id FROM {self.schema}.repositories""",
        )

    @lru_cache
    def repository_node_ids_for_org(self, org_login: str):
        return self._find_all_objects(
            f"""SELECT node_id FROM {self.schema}.repositories WHERE org_login = ?""",
            [org_login],
        )

    @lru_cache
    def private_repository_node_ids(self):
        return self._find_all_objects(
            f"""SELECT node_id FROM {self.schema}.repositories WHERE visibility = 'private' or visibility = 'internal'""",
        )

    @lru_cache
    def private_repository_node_ids_for_org(self, org_login: str):
        return self._find_all_objects(
            f"""SELECT node_id FROM {self.schema}.repositories WHERE org_login = ? AND (visibility = 'private' or visibility = 'internal')""",
            [org_login],
        )

    @lru_cache
    def actions_enabled_repository_node_ids_for_org(self, org_login: str):
        return self._find_all_objects(
            f"""SELECT node_id FROM {self.schema}.repositories WHERE org_login = ? AND actions_enabled = true""",
            [org_login],
        )

    @lru_cache
    def actions_enabled_repositories_for_org(self, org_login: str) -> str | None:
        return self._find_single_object(
            f"""SELECT actions_enabled_repositories FROM {self.schema}.organizations WHERE login = ?""",
            [org_login],
        )

    @lru_cache
    def branch_node_ids_for_org(self, org_login: str):
        return self._find_all_objects(
            f"""
            SELECT b.repository_node_id, b.id
            FROM {self.schema}.branches b
            JOIN {self.schema}.repositories r
              ON r.node_id = b.repository_node_id
            WHERE r.org_login = ?
            """,
            [org_login],
        )

    @lru_cache
    def repository_branch_ruleset_count(self, repository_node_id: str) -> int | None:
        row = self._find_single_row(
            f"""SELECT branch_ruleset_count FROM {self.schema}.repositories_graphql WHERE id = ?""",
            [repository_node_id],
        )
        if row is None or row[0] is None:
            return None
        return int(row[0])

    @lru_cache
    def repository_default_branch_collected(self, repository_node_id: str) -> bool:
        """Return whether the repository's REST default branch was collected."""
        row = self._find_single_row(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {self.schema}.repositories r
                JOIN {self.schema}.branches b
                  ON b.repository_node_id = r.node_id
                 AND b.name = r.default_branch
                WHERE r.node_id = ?
                  AND r.default_branch IS NOT NULL
            )
            """,
            [repository_node_id],
        )
        return bool(row and row[0])

    @lru_cache
    def idp(self) -> list:
        return self._find_all_objects(
            f"""SELECT id, issuer, sso_url FROM {self.schema}.saml_provider"""
        )

    @lru_cache
    def idp_for_environment(self, environment_slug: str) -> list:
        return self._find_all_objects(
            f"""SELECT id, issuer, sso_url, environment_node_id, environment_name, environment_type FROM {self.schema}.saml_provider WHERE environment_slug = ?""",
            [environment_slug],
        )

    @lru_cache
    def app_node_id(self, app_slug: str, org_login: str | None = None) -> str | None:
        if org_login is None:
            return self._find_single_object(
                f"""SELECT node_id FROM {self.schema}.applications WHERE slug = ?""",
                [app_slug],
            )

        return self._find_single_object(
            f"""SELECT node_id FROM {self.schema}.applications WHERE slug = ? AND org_login = ?""",
            [app_slug, org_login],
        )

    @lru_cache
    def branches_with_bpr(self, repository_node_id: str):
        """Returns the node_ids of branches that do have a branch protection rule applied."""
        return self._find_all_objects(
            f"""SELECT
                id
            FROM {self.schema}.branches
            WHERE branch_protection_rule IS NOT NULL AND repository_node_id = ?;""",
            [repository_node_id],
        )

    @lru_cache
    def unprotected_branches(self, repository_node_id: str):
        """Returns the node_ids of branches that do not have a branch protection rule applied or have a BPR that does not require approving reviews, does not lock the branch and does not restrict pushes."""
        return self._find_all_objects(
            f"""SELECT
                id
            FROM {self.schema}.unprotected_branches
            WHERE repository_node_id = ?;""",
            [repository_node_id],
        )

    @lru_cache
    def role_can_create_branch(self, role_id: str, repository_node_id: str):
        return self._find_single_object(
            f"""SELECT repository_node_id FROM {self.schema}.role_can_create_branch WHERE id = ? AND repository_node_id = ?""",
            [role_id, repository_node_id],
        )

    @lru_cache
    def members_can_create_repository(self, org_login: str):
        return self._find_single_row(
            f"""SELECT
                members_can_create_repositories,
                members_can_create_public_repositories,
                members_can_create_internal_repositories,
                members_can_create_private_repositories
            FROM {self.schema}.organizations WHERE login = ?""",
            [org_login],
        )

    @lru_cache
    def bypass_pull_request_allowances(self, actor_id: str):
        """Returns the node_ids of users/teams that bypass PR review requirements on branches in a repository (GH_BypassPullRequestAllowances)"""
        return self._find_all_objects(
            f"""SELECT
                rule_id,
            FROM {self.schema}.actor_branch_bypass
            WHERE bypass_type = 'bypass_pull_request_allowances' AND actor_id = ?;""",
            [actor_id],
        )

    @lru_cache
    def bypass_push_restrictions(self, actor_id: str):
        return self._find_all_objects(
            f"""SELECT
                rule_id,
            FROM {self.schema}.actor_branch_bypass
            WHERE bypass_type = 'push_allowances' AND actor_id = ?;""",
            [actor_id],
        )

    @lru_cache
    def _write_combined_bypass(self, repo_node_id: str):
        return self._find_all_objects(
            f"""
            SELECT
                id
            FROM {self.schema}.branch_bpr
            WHERE repository_node_id = ?
                AND (requires_approving_reviews = true OR lock_branch = true)
                AND restricts_pushes = true
                AND is_admin_enforced = false
            """,
            [repo_node_id],
        )

    @lru_cache
    def repo_role_node_ids_with_view_secret_scanning_alerts(
        self, repository_node_id: str
    ):
        return self._find_all_objects(
            f"""
                SELECT repository_node_id || '_' || name
                FROM {self.schema}.repo_roles
                WHERE repository_node_id = ?
                  AND (
                    (type = 'default' AND name = 'admin')
                    OR json_contains(permissions, '"view_secret_scanning_alerts"')
                  )
                """,
            [repository_node_id],
        )

    @lru_cache
    def org_role_node_ids_with_view_secret_scanning_alerts(self, org_login: str):
        return self._find_all_objects(
            f"""
             SELECT org_node_id || '_' || name
             FROM {self.schema}.org_roles
             WHERE org_login = ?
               AND (
                 (type = 'default' AND name = 'owners')
                 OR json_contains(permissions, '"view_secret_scanning_alerts"')
               )
             """,
            [org_login],
        )

    @lru_cache
    def actor_gate_bypass(
        self,
        actor_node_id: str,
        repo_node_id: str,
        role_has_bypass_branch_protection: bool,
        role_has_push_protected_branch: bool,
    ):
        return self._find_all_objects(
            f"""
            SELECT DISTINCT branch_id
            FROM {self.schema}.actor_branch_gates
            WHERE actor_id = ? AND repository_node_id = ?
              AND (
                (requires_approving_reviews = false AND lock_branch = false)
                OR (has_pr_allowance = true AND lock_branch = false AND is_admin_enforced = false)
                OR (? AND is_admin_enforced = false)
              )
              AND (
                restricts_pushes = false
                OR has_push_allowance = true
                OR ?
              )
            """,
            [
                actor_node_id,
                repo_node_id,
                role_has_bypass_branch_protection,
                role_has_push_protected_branch,
            ],
        )

    @lru_cache
    def _write_push_restricted_branch_bypass(self, repo_node_id: str):
        return self._find_all_objects(
            f"""
            SELECT
                id
            FROM {self.schema}.branch_bpr
            WHERE restricts_pushes IS true AND repository_node_id = ?
            AND requires_approving_reviews = false AND lock_branch = false
            ;""",
            [repo_node_id],
        )

    @lru_cache
    def _write_branch_protection_bypass(self, repo_node_id: str):
        return self._find_all_objects(
            f"""
            SELECT
                id
            FROM {self.schema}.branch_bpr
            WHERE repository_node_id = ?
                AND (requires_approving_reviews = true or lock_branch = true)
                AND is_admin_enforced = false
                AND restricts_pushes IS false
            """,
            [repo_node_id],
        )

    @lru_cache
    def _write_admin_bypass(self, repo_node_id: str):
        return self._find_all_objects(
            f"""
            SELECT
                id
            FROM {self.schema}.branch_bpr
            WHERE repository_node_id = ?
                AND (requires_approving_reviews = true or restricts_pushes = true or lock_branch = true)
                AND is_admin_enforced = false
            """,
            [repo_node_id],
        )

    @lru_cache
    def org_secret(self, secret_name: str, org_login: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.organization_secrets
            WHERE name = ? AND org_login = ?
            """,
            [secret_name, org_login],
        )

    @lru_cache
    def repo_secret(self, secret_name: str, repository_id: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.repository_secrets
            WHERE name = ? AND repository_node_id = ?
            """,
            [secret_name, repository_id],
        )

    @lru_cache
    def environment_secret(self, secret_name: str, repository_id: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.environment_secrets
            WHERE name = ? AND repository_node_id = ?
            """,
            [secret_name, repository_id],
        )

    @lru_cache
    def environment_secret_for_environment(
        self, secret_name: str, repository_id: str, environment_name: str
    ):
        return self._find_single_object(
            f"""
             SELECT name FROM {self.schema}.environment_secrets
             WHERE name = ? AND repository_node_id = ? AND environment_name = ?
             """,
            [secret_name, repository_id, environment_name],
        )

    @lru_cache
    def org_variable(self, var_name: str, org_login: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.organization_variables
            WHERE name = ? AND org_login = ?
            """,
            [var_name, org_login],
        )

    @lru_cache
    def repo_variable(self, var_name: str, repository_id: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.repository_variables
            WHERE name = ? AND repository_node_id = ?
            """,
            [var_name, repository_id],
        )

    @lru_cache
    def environment_variable(self, var_name: str, repository_id: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.environment_variables
            WHERE name = ? AND repository_node_id = ?
            """,
            [var_name, repository_id],
        )

    @lru_cache
    def environment_variable_for_environment(
        self, var_name: str, repository_id: str, environment_name: str
    ):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.environment_variables
            WHERE name = ? AND repository_node_id = ? AND environment_name = ?
            """,
            [var_name, repository_id, environment_name],
        )

    @lru_cache
    def environment(self, env_name: str, repository_id: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.environments
            WHERE name = ? AND repository_node_id = ?
            """,
            [env_name, repository_id],
        )

    @lru_cache
    def environment_deployment_branch_policy(
        self, environment_name: str, repository_node_id: str
    ) -> tuple[bool, bool] | None:
        return self._find_single_row(
            f"""SELECT
                coalesce(deployment_branch_policy->>'protected_branches', 'false') = 'true' AS protected_branches,
                coalesce(deployment_branch_policy->>'custom_branch_policies', 'false') = 'true' AS custom_branch_policies
            FROM {self.schema}.environments
            WHERE name = ? AND repository_node_id = ?""",
            [environment_name, repository_node_id],
        )

    @lru_cache
    def environment_deployment_reviewer_policy(
        self, environment_name: str, repository_node_id: str
    ) -> tuple[bool, bool] | None:
        return self._find_single_row(
            f"""SELECT
                EXISTS (
                    SELECT 1
                    FROM json_each(e.protection_rules) AS rule
                    WHERE json_extract_string(rule.value, '$.type') = 'required_reviewers'
                ) AS required_reviewers,
                coalesce((
                    SELECT json_extract_string(rule.value, '$.prevent_self_review') = 'true'
                    FROM json_each(e.protection_rules) AS rule
                    WHERE json_extract_string(rule.value, '$.type') = 'required_reviewers'
                    LIMIT 1
                ), false) AS prevent_self_review
            FROM {self.schema}.environments e
            WHERE e.name = ? AND e.repository_node_id = ?""",
            [environment_name, repository_node_id],
        )

    @lru_cache
    def workflow(self, repository_node_id: str, path: str):
        return self._find_single_object(
            f"""
            SELECT name FROM {self.schema}.workflows
            WHERE repository_node_id = ? AND path = ?
            """,
            [repository_node_id, path],
        )

    @lru_cache
    def branches_for_repository(self, repository_node_id: str):
        return self._find_all_objects(
            f"""SELECT
                id,
                name,
                branch_protection_rule IS NOT NULL AS protected
            FROM {self.schema}.branches
            WHERE repository_node_id = ?""",
            [repository_node_id],
        )

    @lru_cache
    def environment_branch_policy_names(self, environment_node_id: str):
        return self._find_all_objects(
            f"""
            SELECT name
            FROM {self.schema}.environment_branch_policies
            WHERE environment_node_id = ?
            """,
            [environment_node_id],
        )

    @lru_cache
    def reviewer_repo_role_assignments(
        self, reviewer_node_id: str, reviewer_kind: str, repository_node_id: str
    ):
        reviewer_kind = reviewer_kind.lower()
        return self._find_all_objects(
            f"""
            WITH RECURSIVE
            repository_org(org_login) AS (
                SELECT org_login
                FROM {self.schema}.repositories
                WHERE node_id = ?
            ),
            seed_teams(team_id) AS (
                SELECT ? WHERE ? = 'team'

                UNION

                SELECT tm.team_id
                FROM {self.schema}.team_members tm
                WHERE ? = 'user'
                  AND tm.id = ?
            ),
            actor_teams(team_id) AS (
                SELECT team_id
                FROM seed_teams

                UNION

                SELECT json_extract_string(t.parent_team, '$.id')
                FROM {self.schema}.teams t
                JOIN actor_teams actor_team ON t.id = actor_team.team_id
                WHERE t.parent_team IS NOT NULL
                  AND json_extract_string(t.parent_team, '$.id') IS NOT NULL
            ),
            direct_repo_roles(
                assignment_actor_id,
                role_id,
                role_name,
                base_role,
                role_permissions
            ) AS (
                SELECT DISTINCT
                    rra.node_id,
                    rr.id,
                    rra.role_name,
                    coalesce(rra.base_role, rr.base_role),
                    rra.role_permissions
                FROM {self.schema}.repo_role_assignments rra
                LEFT JOIN {self.schema}.repo_roles rr
                  ON rr.repository_node_id = rra.repo_node_id
                 AND rr.name = rra.role_name
                WHERE rra.repo_node_id = ?
                  AND (
                      (lower(rra.assignee_type) = ? AND rra.node_id = ?)
                      OR (
                          lower(rra.assignee_type) = 'team'
                          AND rra.node_id IN (SELECT team_id FROM actor_teams)
                      )
                  )
            ),
            actor_org_roles(assignment_actor_id, org_role_name, base_role) AS (
                SELECT
                    u.id,
                    CASE WHEN u.role = 'ADMIN' THEN 'owners' ELSE 'members' END,
                    org_role.base_role
                FROM {self.schema}.users u
                JOIN repository_org repo_org ON repo_org.org_login = u.org_login
                JOIN {self.schema}.org_roles org_role
                  ON org_role.org_login = u.org_login
                 AND org_role.name = CASE
                     WHEN u.role = 'ADMIN' THEN 'owners'
                     ELSE 'members'
                 END
                WHERE ? = 'user'
                  AND u.id = ?

                UNION

                SELECT
                    orm.node_id,
                    orm.org_role_name,
                    org_role.base_role
                FROM {self.schema}.org_role_members orm
                JOIN repository_org repo_org ON repo_org.org_login = orm.org_login
                JOIN {self.schema}.org_roles org_role
                  ON org_role.org_login = orm.org_login
                 AND org_role.name = orm.org_role_name
                WHERE ? = 'user'
                  AND orm.node_id = ?

                UNION

                SELECT
                    ort.node_id,
                    ort.org_role_name,
                    org_role.base_role
                FROM {self.schema}.org_role_teams ort
                JOIN repository_org repo_org ON repo_org.org_login = ort.org_login
                JOIN {self.schema}.org_roles org_role
                  ON org_role.org_login = ort.org_login
                 AND org_role.name = ort.org_role_name
                WHERE ort.node_id IN (SELECT team_id FROM actor_teams)
            ),
            org_repo_roles(
                assignment_actor_id,
                role_id,
                role_name,
                base_role,
                role_permissions
            ) AS (
                SELECT DISTINCT
                    actor_org_role.assignment_actor_id,
                    rr.id,
                    rr.name,
                    rr.base_role,
                    rr.permissions
                FROM actor_org_roles actor_org_role
                JOIN {self.schema}.repo_roles rr
                  ON rr.repository_node_id = ?
                 AND rr.name = actor_org_role.base_role
            )
            SELECT * FROM direct_repo_roles
            UNION
            SELECT * FROM org_repo_roles
            """,
            [
                repository_node_id,
                reviewer_node_id,
                reviewer_kind,
                reviewer_kind,
                reviewer_node_id,
                repository_node_id,
                reviewer_kind,
                reviewer_node_id,
                reviewer_kind,
                reviewer_node_id,
                reviewer_kind,
                reviewer_node_id,
                repository_node_id,
            ],
        )

    @staticmethod
    def _role_permissions(raw_permissions) -> set[str]:
        if raw_permissions is None:
            return set()
        if isinstance(raw_permissions, str):
            try:
                raw_permissions = json.loads(raw_permissions)
            except json.JSONDecodeError:
                return set()
        if not isinstance(raw_permissions, list):
            return set()
        return {str(permission) for permission in raw_permissions}

    @lru_cache
    def reviewer_deployment_path(
        self,
        reviewer_node_id: str,
        reviewer_kind: str,
        repository_node_id: str,
        eligible_branch_ids: tuple[str, ...],
        allow_create_branch: bool,
    ) -> tuple[str, str | None] | None:
        if not self.repository_default_branch_collected(repository_node_id):
            return None

        eligible_branches = set(eligible_branch_ids)
        write_roles = {"write", "maintain", "admin"}
        bypass_roles = {"maintain"}

        for (
            assignment_actor_id,
            role_id,
            role_name,
            base_role,
            raw_permissions,
        ) in self.reviewer_repo_role_assignments(
            reviewer_node_id, reviewer_kind, repository_node_id
        ):
            permissions = self._role_permissions(raw_permissions)
            has_write_access = role_name in write_roles or base_role in write_roles
            if not has_write_access:
                continue

            if (
                allow_create_branch
                and role_id is not None
                and self.role_can_create_branch(role_id, repository_node_id)
            ):
                return ("create_branch", None)

            writable_branches = {
                branch_id
                for (branch_id,) in self.unprotected_branches(repository_node_id)
            }

            has_push_protected_branch = (
                ("push_protected_branch" in permissions and base_role in write_roles)
                or role_name in bypass_roles
                or base_role in bypass_roles
            )
            has_bypass_branch_protection = (
                "bypass_branch_protection" in permissions and base_role in write_roles
            )

            if role_name == "admin" or base_role == "admin":
                writable_branches.update(
                    branch_id
                    for (branch_id,) in self._write_admin_bypass(repository_node_id)
                )
            if has_push_protected_branch:
                writable_branches.update(
                    branch_id
                    for (branch_id,) in self._write_push_restricted_branch_bypass(
                        repository_node_id
                    )
                )
            if has_bypass_branch_protection:
                writable_branches.update(
                    branch_id
                    for (branch_id,) in self._write_branch_protection_bypass(
                        repository_node_id
                    )
                )
            if has_push_protected_branch and has_bypass_branch_protection:
                writable_branches.update(
                    branch_id
                    for (branch_id,) in self._write_combined_bypass(repository_node_id)
                )

            writable_branches.update(
                branch_id
                for (branch_id,) in self.actor_gate_bypass(
                    assignment_actor_id,
                    repository_node_id,
                    has_bypass_branch_protection,
                    has_push_protected_branch,
                )
            )

            for branch_id in eligible_branch_ids:
                if branch_id in writable_branches and branch_id in eligible_branches:
                    return ("write_branch", branch_id)

        return None

    @lru_cache
    def members_can_fork_private_repositories(self, org_login: str):
        return self._find_all_objects(
            f"""SELECT members_can_fork_private_repositories FROM {self.schema}.organizations WHERE login = ?""",
            [org_login],
        )

    @lru_cache
    def repository_allow_forking(
        self, repository_node_id: str
    ) -> tuple[str, bool] | None:
        return self._find_single_row(
            f"""SELECT visibility, allow_forking FROM {self.schema}.repositories WHERE node_id = ?""",
            [repository_node_id],
        )

    @lru_cache
    def repo_role_node_ids_with_read_repo_contents(self, repository_node_id: str):
        return self._find_all_objects(
            f"""
            SELECT repository_node_id || '_' || name
            FROM {self.schema}.repo_roles
            WHERE repository_node_id = ?
              AND type = 'default'
              AND name IN ('read', 'write', 'admin')
            """,
            [repository_node_id],
        )
