# GH_WriteOrganizationActionsVariables

## General Information

The non-traversable GH_WriteOrganizationActionsVariables edge represents that a role can write organization-level GitHub Actions variables. This edge is dynamically generated from custom organization role permissions discovered by the collector. Organization-level variables are available to workflows across multiple repositories and often contain configuration values such as environment URLs, feature flags, and service endpoints. An attacker with this permission could overwrite existing variables to redirect workflows to malicious endpoints or alter application behavior.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_WriteOrganizationActionsVariables| n1
```
