# GH_TransferRepository

## General Information

The non-traversable GH_TransferRepository edge represents that a role has the ability to transfer repositories to or from the organization. This permission is typically restricted to Owners, as transferring a repository can move it outside of the organization's security controls, branch protection rules, and audit logging. An attacker with this permission could transfer a repository to an organization they control, effectively exfiltrating the codebase and its associated secrets.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_TransferRepository| n1
```
