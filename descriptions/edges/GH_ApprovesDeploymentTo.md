## General Information

The non-traversable GH_ApprovesDeploymentTo edge represents that a user or team is configured as a required reviewer for a GitHub Environment.

This edge is emitted from GH_User or GH_Team nodes to GH_Environment nodes when the environment includes a required reviewer protection rule. Required reviewers act as an approval gate before jobs referencing the environment can continue.

The edge is non-traversable because being listed as a reviewer does not by itself grant deployment access, but it is important context for understanding how deployments are approved and which identities participate in environment protection workflows.
