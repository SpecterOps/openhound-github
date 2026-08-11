## Description

Represents a self-hosted runner group visible within a GitHub organization. Organization runner groups may either be native to the organization or inherited from an enterprise runner group.

Native organization runner groups contain GH_OrgRunner nodes directly. Inherited organization runner groups do not directly contain organization runners; instead, they link to the source GH_EnterpriseRunnerGroup through GH_InheritedFrom and gain access to the enterprise runners contained there. GH_GrantsAccessTo edges describe which repositories may use the runners exposed by the group.
