import duckdb

from openhound_github.models.saml import (
    org_saml_acs_row,
    org_saml_issuer_row,
    org_saml_service_provider_row,
)
from openhound_github.transforms import transforms


ORG_SAML_PROVIDER_ROW = {
    "id": "MDQ6U2FtbElkZW50aXR5UHJvdmlkZXIx",
    "issuer": "https://sts.windows.net/example/",
    "org_login": "kng-emea",
    "org_name": "KNG EMEA",
    "org_node_id": "O_kgDOExample",
}


def test_org_saml_row_builders_accept_dlt_mapping_rows() -> None:
    service_provider = org_saml_service_provider_row(ORG_SAML_PROVIDER_ROW)
    issuer = org_saml_issuer_row(ORG_SAML_PROVIDER_ROW)
    acs = org_saml_acs_row(ORG_SAML_PROVIDER_ROW)

    assert service_provider == {
        "id": "github:saml:sp:org:kng-emea",
        "native_id": "O_kgDOExample",
        "scope_type": "organization",
        "scope_slug": "kng-emea",
        "saml_provider_id": "MDQ6U2FtbElkZW50aXR5UHJvdmlkZXIx",
        "issuer_id": "github:saml:trusted-issuer:org:kng-emea",
        "acs_id": "github:saml:acs:org:kng-emea",
        "enabled": True,
    }
    assert issuer == {
        "id": "github:saml:trusted-issuer:org:kng-emea",
        "native_id": "O_kgDOExample",
        "scope_type": "organization",
        "scope_slug": "kng-emea",
        "entity_id": "https://sts.windows.net/example/",
    }
    assert acs == {
        "id": "github:saml:acs:org:kng-emea",
        "native_id": "O_kgDOExample",
        "scope_type": "organization",
        "scope_slug": "kng-emea",
        "acs_url": "https://github.com/orgs/kng-emea/saml/consume",
        "sp_entity_id": "https://github.com/orgs/kng-emea",
    }


def test_transforms_create_zero_row_optional_branch_inputs() -> None:
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA github")
    con.execute(
        "CREATE TABLE github.branches (id VARCHAR, repository_node_id VARCHAR)"
    )
    con.execute(
        "CREATE TABLE github.repo_roles (id BIGINT, repository_node_id VARCHAR)"
    )

    transforms(con)

    for table in (
        "branches",
        "branch_protection_rules",
        "repo_roles",
        "branch_bpr",
        "actor_branch_bypass",
        "unprotected_branches",
        "actor_branch_gates",
        "role_can_create_branch",
    ):
        assert con.execute(f"SELECT COUNT(*) FROM github.{table}").fetchone() == (0,)
