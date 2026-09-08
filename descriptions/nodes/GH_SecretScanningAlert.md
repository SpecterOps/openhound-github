# GH_SecretScanningAlert

## General Information

Represents a GitHub secret scanning alert detected in a repository. Secret scanning alerts are raised when GitHub detects a known secret pattern (such as an API key, token, or credential) committed to a repository. The alert captures the secret type, validity status, and current resolution state.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `repository_name` | `string` | The name of the repository where the secret was detected. |
| `secret_type` | `string` | The type of secret detected (e.g., `github_personal_access_token`, `aws_access_key_id`). |
| `secret_type_display_name` | `string` | A human-readable name for the secret type. |
| `validity` | `string` | The validity status of the detected secret (e.g., `active`, `inactive`, `unknown`). |
| `state` | `string` | The alert state (e.g., `open`, `resolved`). |
| `url` | `string` | The HTML URL to view the alert on GitHub. |
| `query_repository` | `string` | Query for repository. |
| `query_alert_viewers` | `string` | Query for alert viewers. |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_SecretScanningAlert"]
    n2["GH_Organization"]
    n3["GH_RepoRole"]
    n4["GH_Repository"]
    n5["GH_User"]
    n0 -->|GH_CanReadSecretScanningAlert| n1
    n2 -.->|GH_Contains| n1
    n3 -->|GH_CanReadSecretScanningAlert| n1
    n4 -.->|GH_Contains| n1
    n1 -->|GH_ValidToken| n5
```
