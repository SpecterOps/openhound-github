# GH_ManageWebhooks

## General Information

The non-traversable GH_ManageWebhooks edge represents a role's ability to create, modify, and delete repository-level webhooks. This permission is available to Admin roles and custom roles that have been granted this specific permission. Webhooks can exfiltrate repository events and code changes to external endpoints, making this a security-sensitive permission. An attacker with this permission could configure a webhook to receive push event payloads containing commit diffs, effectively creating a covert channel for data exfiltration.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ManageWebhooks| n1
```
