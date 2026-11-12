# GH_SecretScanningAlert

## General Information

Represents a GitHub secret scanning alert detected in a repository. Secret scanning alerts are raised when GitHub detects a known secret pattern (such as an API key, token, or credential) committed to a repository. The alert captures the secret type, validity status, and current resolution state.

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_SecretScanningAlert"]
    n2["GH_Organization"]
    n3["GH_RepoRole"]
    n4["GH_Repository"]
    n5["GH_User"]
    n0 -->|GH_CanReadSecretScanningAlert| n1
    n2 -.->|GH_Contains| n1
    n3 -->|GH_CanReadSecretScanningAlert| n1
    n4 -.->|GH_Contains| n1
    n1 -->|GH_ValidToken| n5
```

## References

- [Secret scanning API](https://docs.github.com/en/rest/secret-scanning/secret-scanning)
