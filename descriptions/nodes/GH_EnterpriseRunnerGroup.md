## Description

Represents a self-hosted runner group owned by a GitHub Enterprise account. Enterprise runner groups control which organizations may use a shared set of enterprise runners. Groups with `visibility=all` are assigned to every organization in the enterprise, while groups with `visibility=selected` are assigned only to explicitly selected organizations.

Enterprise runner groups contain GH_EnterpriseRunner nodes and may be projected into organizations as inherited GH_OrgRunnerGroup nodes. The GH_InheritedFrom edge links the organization view back to the enterprise-owned group.
