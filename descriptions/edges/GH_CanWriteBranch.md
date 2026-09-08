# GH_CanWriteBranch

## General Information

The traversable GH_CanWriteBranch edge is a computed edge indicating that a role or actor can push to a specific branch. The computation evaluates both the merge gate (PR review requirements) and push gate (push restrictions) of any branch protection rule protecting the branch. Role-level edges are the common case; per-actor edges from GH_User or GH_Team are only emitted when BPR allowances grant access beyond what the role provides. Each edge includes a `reason` property (`no_protection`, `admin`, `push_protected_branch`, `bypass_branch_protection`, `push_allowance`, `bypass_pr_allowance`) and a `query_composition` Cypher query showing the underlying graph evidence.

## Scenarios

### `no_protection` — Unprotected branch

Branch has no BPR. Any write-capable role can push directly.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Branch` | `false` |
| `GH_Team` | `GH_Branch` | `false` |
| `GH_User` | `GH_Branch` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Branch"]
    n2["GH_Team"]
    n3["GH_User"]
    n0 -.->|GH_CanWriteBranch| n1
    n2 -.->|GH_CanWriteBranch| n1
    n3 -.->|GH_CanWriteBranch| n1
```
