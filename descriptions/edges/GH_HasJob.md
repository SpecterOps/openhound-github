## General Information

The traversable `GH_HasJob` edge links a workflow to each of its jobs. This edge is the primary structural link for walking from a workflow definition into its execution units. Because jobs can declare environments and permissions, traversing this edge enables analysts to reason about what a workflow can do and where it can deploy.
