# GH_Contains

## General Information

The non-traversable GH_Contains edge represents structural containment within the GitHub resource hierarchy. The enterprise contains enterprise teams, roles, managed users, runner groups, and enterprise runners through their groups. The organization serves as a top-level container for users, teams, repositories, roles, scopes, secrets, app installations, personal access tokens, and organization runner groups. Native organization runner groups contain organization runners. Repositories contain branches, workflows, branch protection rules, environments, repo-level secrets and variables, and repository-scoped runners. Environments contain environment branch policies, environment-scoped secrets, and environment-scoped variables. This edge is created by the collector to establish the resource hierarchy and is not traversable because containment alone does not imply privilege escalation.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_Enterprise` | `GH_EnterpriseRole` | `false` |
| `GH_Enterprise` | `GH_EnterpriseRunnerGroup` | `false` |
| `GH_Enterprise` | `GH_EnterpriseTeam` | `false` |
| `GH_Enterprise` | `GH_Organization` | `false` |
| `GH_EnterpriseRunnerGroup` | `GH_EnterpriseRunner` | `false` |
| `GH_Environment` | `GH_EnvironmentBranchPolicy` | `false` |
| `GH_Environment` | `GH_EnvironmentSecret` | `false` |
| `GH_Environment` | `GH_EnvironmentVariable` | `false` |
| `GH_OrgRunnerGroup` | `GH_OrgRunner` | `false` |
| `GH_Organization` | `GH_AppInstallation` | `false` |
| `GH_Organization` | `GH_OrgRole` | `false` |
| `GH_Organization` | `GH_OrgRunnerGroup` | `false` |
| `GH_Organization` | `GH_OrgSecret` | `false` |
| `GH_Organization` | `GH_OrgVariable` | `false` |
| `GH_Organization` | `GH_PersonalAccessToken` | `false` |
| `GH_Organization` | `GH_PersonalAccessTokenRequest` | `false` |
| `GH_Organization` | `GH_Scope` | `false` |
| `GH_Organization` | `GH_SecretScanningAlert` | `false` |
| `GH_Repository` | `GH_Branch` | `false` |
| `GH_Repository` | `GH_BranchProtectionRule` | `false` |
| `GH_Repository` | `GH_DeployKey` | `false` |
| `GH_Repository` | `GH_Environment` | `false` |
| `GH_Repository` | `GH_RepoRunner` | `false` |
| `GH_Repository` | `GH_RepoSecret` | `false` |
| `GH_Repository` | `GH_RepoVariable` | `false` |
| `GH_Repository` | `GH_SecretScanningAlert` | `false` |
| `GH_Repository` | `GH_Workflow` | `false` |
| `GH_Workflow` | `GH_WorkflowJob` | `false` |
| `GH_WorkflowJob` | `GH_WorkflowStep` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseRole"]
    n2["GH_EnterpriseRunnerGroup"]
    n3["GH_EnterpriseTeam"]
    n4["GH_Organization"]
    n5["GH_EnterpriseRunner"]
    n6["GH_Environment"]
    n7["GH_EnvironmentBranchPolicy"]
    n8["GH_EnvironmentSecret"]
    n9["GH_EnvironmentVariable"]
    n10["GH_OrgRunnerGroup"]
    n11["GH_OrgRunner"]
    n12["GH_AppInstallation"]
    n13["GH_OrgRole"]
    n14["GH_OrgSecret"]
    n15["GH_OrgVariable"]
    n16["GH_PersonalAccessToken"]
    n17["GH_PersonalAccessTokenRequest"]
    n18["GH_Scope"]
    n19["GH_SecretScanningAlert"]
    n20["GH_Repository"]
    n21["GH_Branch"]
    n22["GH_BranchProtectionRule"]
    n23["GH_DeployKey"]
    n24["GH_RepoRunner"]
    n25["GH_RepoSecret"]
    n26["GH_RepoVariable"]
    n27["GH_Workflow"]
    n28["GH_WorkflowJob"]
    n29["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n0 -.->|GH_Contains| n2
    n0 -.->|GH_Contains| n3
    n0 -.->|GH_Contains| n4
    n2 -.->|GH_Contains| n5
    n6 -.->|GH_Contains| n7
    n6 -.->|GH_Contains| n8
    n6 -.->|GH_Contains| n9
    n10 -.->|GH_Contains| n11
    n4 -.->|GH_Contains| n12
    n4 -.->|GH_Contains| n13
    n4 -.->|GH_Contains| n10
    n4 -.->|GH_Contains| n14
    n4 -.->|GH_Contains| n15
    n4 -.->|GH_Contains| n16
    n4 -.->|GH_Contains| n17
    n4 -.->|GH_Contains| n18
    n4 -.->|GH_Contains| n19
    n20 -.->|GH_Contains| n21
    n20 -.->|GH_Contains| n22
    n20 -.->|GH_Contains| n23
    n20 -.->|GH_Contains| n6
    n20 -.->|GH_Contains| n24
    n20 -.->|GH_Contains| n25
    n20 -.->|GH_Contains| n26
    n20 -.->|GH_Contains| n19
    n20 -.->|GH_Contains| n27
    n27 -.->|GH_Contains| n28
    n28 -.->|GH_Contains| n29
```
