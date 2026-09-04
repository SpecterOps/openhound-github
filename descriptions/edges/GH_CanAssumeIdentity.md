# GH_CanAssumeIdentity

## General Information

The traversable GH_CanAssumeIdentity edge is a hybrid edge connecting GitHub OIDC token sources to cloud identity targets configured for GitHub Actions federation. This edge represents a verified path from GitHub Actions to cloud resource access. It is traversable because an attacker who can execute workflows in the source repository, branch, or environment can obtain an OIDC token that the cloud provider will accept, granting access to the associated cloud identity and its permissions. This edge is critical for identifying cross-cloud lateral movement paths from GitHub into Azure and AWS.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_Repository` | `External cloud identity` | `true` |

## Diagram

```mermaid
graph LR
    n0["GH_Repository"]
    n1["External cloud identity"]
    n0 -->|GH_CanAssumeIdentity| n1
```
