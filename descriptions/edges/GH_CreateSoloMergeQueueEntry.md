# GH_CreateSoloMergeQueueEntry

## General Information

The non-traversable GH_CreateSoloMergeQueueEntry edge represents a role's ability to create solo merge queue entries, effectively bypassing the merge queue by merging independently of other queued changes. This permission is available to Admin roles and custom roles that have been granted this specific permission. Solo merge queue entries skip the batching and ordering guarantees of the merge queue, allowing changes to land without waiting for or being tested alongside other pending merges. This can circumvent the integration testing benefits that merge queues provide.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_CreateSoloMergeQueueEntry| n1
```
