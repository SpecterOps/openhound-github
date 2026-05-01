MEMBERS_WITH_ROLE_QUERY = """
query MembersWithRole($login: String!, $count: Int!, $after: String) {
    organization(login: $login) {
        membersWithRole(first: $count, after: $after) {
            edges {
                role
                node {
                    id
                    databaseId
                    login
                    name
                    email
                    company
                }
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}
"""

ENTERPRISE_QUERY = """
query Enterprise($slug: String!, $after: String) {
    enterprise(slug: $slug) {
        id
        databaseId
        name
        slug
        description
        location
        url
        websiteUrl
        createdAt
        updatedAt
        billingEmail
        securityContactEmail
        viewerIsAdmin
        organizations(first: 100, after: $after) {
            nodes {
                id
                login
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    }
}
"""

ENTERPRISE_MEMBERS_QUERY = """
query EnterpriseMembers($slug: String!, $count: Int = 100, $after: String = null) {
    enterprise(slug: $slug) {
        members(first: $count, after: $after) {
            edges {
                node {
                    __typename
                    ... on User {
                        id
                        databaseId
                        login
                        name
                        email
                        company
                    }
                    ... on EnterpriseUserAccount {
                        id
                        login
                        name
                        url
                        createdAt
                        updatedAt
                        user {
                            id
                            databaseId
                            login
                            name
                            email
                            company
                        }
                    }
                }
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}
"""

ENTERPRISE_ADMINS_QUERY = """
query EnterpriseAdmins($slug: String!, $count: Int = 100, $after: String = null) {
    enterprise(slug: $slug) {
        ownerInfo {
            admins(first: $count, after: $after) {
                edges {
                    node {
                        id
                        login
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
}
"""

ENTERPRISE_SAML_QUERY = """
query EnterpriseSAML($slug: String!, $count: Int = 100, $after: String = null) {
    enterprise(slug: $slug) {
        id
        name
        slug
        ownerInfo {
            samlIdentityProvider {
                id
                issuer
                ssoUrl
                digestMethod
                signatureMethod
                idpCertificate
                externalIdentities(first: $count, after: $after) {
                    totalCount
                    nodes {
                        guid
                        id
                        samlIdentity {
                            familyName
                            givenName
                            nameId
                            username
                        }
                        scimIdentity {
                            username
                            givenName
                            familyName
                            emails {
                                value
                                primary
                                type
                            }
                        }
                        user {
                            id
                            login
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }
    }
}
"""

TEAMS_QUERY = """
query Teams($login: String!, $count: Int!, $after: String) {
    organization(login: $login) {
        id
        login
        teams(first: $count, after: $after) {
            nodes {
                id
                databaseId
                name
                slug
                description
                privacy
                parentTeam {
                    id
                }
                members(first: 100, membership: IMMEDIATE) {
                    edges {
                        role
                        node {
                            id
                            login
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}
"""

TEAM_MEMBERS_OVERFLOW_QUERY = """
query TeamMembersOverflow($login: String!, $slug: String!, $count: Int!, $after: String!) {
    organization(login: $login) {
        team(slug: $slug) {
            members(first: $count, after: $after, membership: IMMEDIATE) {
                edges {
                    role
                    node {
                        id
                        login
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
}
"""

REPO_REFS_QUERY = """
query RepoRefs($login: String!, $count: Int!, $after: String) {
    organization(login: $login) {
        repositories(first: $count, after: $after) {
            nodes {
                id
                name
                refs(first: 100, refPrefix: "refs/heads/") {
                    nodes {
                        id
                        name
                        target { oid }
                        branchProtectionRule { id }
                    }
                    pageInfo { endCursor hasNextPage }
                }
            }
            pageInfo { endCursor hasNextPage }
        }
    }
}
"""

REF_OVERFLOW_QUERY = """
query RefOverflow($owner: String!, $name: String!, $count: Int!, $after: String!) {
    repository(owner: $owner, name: $name) {
        refs(first: $count, refPrefix: "refs/heads/", after: $after) {
            nodes {
                id
                name
                target { oid }
                branchProtectionRule { id }
            }
            pageInfo { endCursor hasNextPage }
        }
    }
}
"""

PROTECTION_RULES_QUERY = """
query ProtectionRulesByIds($ids: [ID!]!) {
    nodes(ids: $ids) {
        ... on BranchProtectionRule {
            id
            pattern
            isAdminEnforced
            lockBranch
            blocksCreations
            requiresApprovingReviews
            requiredApprovingReviewCount
            requiresCodeOwnerReviews
            requireLastPushApproval
            restrictsPushes
            requiresStatusChecks
            requiresStrictStatusChecks
            dismissesStaleReviews
            allowsForcePushes
            allowsDeletions
            bypassPullRequestAllowances(first: 100) {
                nodes {
                    actor {
                        ... on User { id login }
                        ... on Team { id slug }
                    }
                }
            }
            pushAllowances(first: 100) {
                nodes {
                    actor {
                        ... on User { id login }
                        ... on Team { id slug }
                    }
                }
            }
        }
    }
}
"""

SAML_QUERY = """
query SAMLProvider($login: String!) {
    organization(login: $login) {
        id
        name
        samlIdentityProvider {
            id
            issuer
            ssoUrl
            idpCertificate
            signatureMethod
            digestMethod
        }
    }
}
"""

SAML_IDENTITIES_QUERY = """
query SAMLIdentities($login: String!, $count: Int!, $after: String) {
    organization(login: $login) {
        samlIdentityProvider {
            externalIdentities(first: $count, after: $after) {
                nodes {
                    guid
                    id
                    samlIdentity {
                        familyName
                        givenName
                        nameId
                        username
                    }
                    scimIdentity {
                        familyName
                        givenName
                        username
                    }
                    user {
                        id
                        login
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
}
"""
