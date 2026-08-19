## Description

Represents a self-hosted runner group owned by a GitHub Enterprise account. Enterprise runner groups control which organizations may use a shared set of enterprise runners. That organization-level visibility is reflected by which inherited GH_OrgRunnerGroup nodes point back to the enterprise group through GH_InheritedFrom.

Enterprise runner groups contain GH_EnterpriseRunner nodes and emit GH_HasRunner for directly assigned runners to represent the traversable capability hop from the group to the runner. They may be projected into organizations as inherited GH_OrgRunnerGroup nodes. The GH_InheritedFrom edge links the organization view back to the enterprise-owned group.
