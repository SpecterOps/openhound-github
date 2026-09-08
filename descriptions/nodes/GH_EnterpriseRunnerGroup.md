# GH_EnterpriseRunnerGroup

## General Information

Represents a self-hosted runner group owned by a GitHub Enterprise account. Enterprise runner groups control which organizations may use a shared set of enterprise runners. That organization-level visibility is reflected by which inherited GH_OrgRunnerGroup nodes point back to the enterprise group through GH_InheritedFrom.

Enterprise runner groups contain GH_EnterpriseRunner nodes and emit GH_HasRunner for directly assigned runners to represent the traversable capability hop from the group to the runner. They may be projected into organizations as inherited GH_OrgRunnerGroup nodes. The GH_InheritedFrom edge links the organization view back to the enterprise-owned group.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `scope` | `string` | Whether the runner group is enterprise or organization scoped. |
| `group_id` | `integer` | The GitHub runner group ID. |
| `group_name` | `string` | The runner group display name. |
| `visibility` | `string` | Which repositories can use this group: `all`, `private`, or `selected`. |
| `default` | `boolean` | Whether this is the default runner group. |
| `inherited` | `boolean` | Whether this runner group is inherited. |
| `allows_public_repositories` | `boolean` | Whether public repositories may use this group. |
| `restricted_to_workflows` | `boolean` | Whether access is restricted to selected workflows. |
| `selected_workflows` | `string` | JSON array of selected workflows, if configured. |
| `runners_url` | `string` | API URL for runners in this group. |
| `selected_organizations_url` | `string` | API URL for organizations assigned to an enterprise group. |
| `environment_name` | `string` | The name of the environment (GitHub organization or enterprise). |
| `query_runners` | `string` | Query for runners. |
| `query_organizations` | `string` | Query for organizations inheriting an enterprise runner group. |
| `query_repositories` | `string` | Query for repositories. |

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseRunnerGroup"]
    n2["GH_EnterpriseRunner"]
    n3["GH_OrgRunnerGroup"]
    n0 -.->|GH_Contains| n1
    n1 -.->|GH_Contains| n2
    n1 -->|GH_HasRunner| n2
    n3 -->|GH_InheritedFrom| n1
```
