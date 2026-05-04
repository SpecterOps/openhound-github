from functools import lru_cache

from duckdb import DuckDBPyConnection
from openhound.core.lookup import LookupManager


class GithubLookup(LookupManager):
    def __init__(self, client: DuckDBPyConnection, schema: str = "github"):
        super().__init__(client, schema)
        self.schema = schema
        self.client = client

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
    def org_login_for_id(self, org_node_id: str) -> str | None:
        return self._find_single_object(
            f"""SELECT login FROM {self.schema}.organizations WHERE node_id = ?""",
            [org_node_id],
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
    def idp(self) -> list:
        return self._find_all_objects(
            f"""SELECT id, issuer, sso_url FROM {self.schema}.saml_provider"""
        )

    @lru_cache
    def idp_for_org(self, org_login: str) -> list:
        return self._find_all_objects(
            f"""SELECT id, issuer, sso_url FROM {self.schema}.saml_provider WHERE org_login = ?""",
            [org_login],
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

    # ROLES TO HERE

    # USERS/TEAMS FROM HERE
    ## GH_BypassPullRequestAllowances
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
