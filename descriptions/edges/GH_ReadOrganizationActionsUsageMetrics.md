# GH_ReadOrganizationActionsUsageMetrics

## General Information

The non-traversable GH_ReadOrganizationActionsUsageMetrics edge represents that a role can read GitHub Actions usage metrics for the organization. This edge is dynamically generated from custom organization role permissions discovered by the collector. Usage metrics provide visibility into workflow execution patterns, runner utilization, and billing data across the organization. While this is primarily an informational permission, it can reveal which repositories have active CI/CD pipelines and the scale of automation in use.

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_ReadOrganizationActionsUsageMetrics| n1
```

## References

- [Organization roles](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization)
- [Custom organization role API](https://docs.github.com/en/enterprise-cloud@latest/rest/orgs/organization-roles)
