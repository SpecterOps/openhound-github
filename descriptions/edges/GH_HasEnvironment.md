## General Information

Environment containment is modeled with the non-traversable GH_Contains edge from a repository to each deployment environment it defines. Branch deployment eligibility is modeled separately with GH_CanDeployToEnvironment and GH_MatchesEnvironmentPolicy rather than a containment edge. Environments are security-relevant because they can gate access to secrets and cloud credentials, and their deployment branch policies control which branches can trigger deployments.
