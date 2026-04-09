## General Information

The non-traversable `GH_DeploysTo` edge links a workflow job to the GitHub Environment it targets via the `environment:` key. Created by `Parse-GitHoundWorkflow`, this edge records which jobs deploy to which environments. Environments can gate deployments with protection rules (required reviewers, wait timers, deployment branch policies) and can expose environment-scoped secrets.
