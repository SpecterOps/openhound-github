"""Conservative classic-protection checks for freely named branch creation.

This is not a general GitHub fnmatch evaluator. Exact branch names and rules
anchored to a literal top-level namespace leave other top-level names available.
Star patterns requiring literal text, such as '*release*', also leave other
names available. Other creation-restricting patterns require actor evaluation rather
than membership in the shared repository scope. In particular, retain the
existing conservative treatment of '*' despite GitHub's FNM_PATHNAME behavior.

Pattern syntax and rule precedence:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule
"""


def branch_creation_restriction(
    pattern: str | None,
    blocks_creations: bool | None,
    restricts_pushes: bool | None,
) -> str | None:
    """Return why a rule excludes shared creation access, or None if it does not.

    Shared eligibility assumes repository write access, without actor-specific
    allowances. A restriction on a finite set of exact names, or on names below
    a literal namespace, still permits freely chosen top-level branch names.
    Star patterns with required literal text can similarly be avoided.
    Unrecognized patterns or missing restriction flags are conservative gaps.
    """
    # GitHub only applies creation restrictions when push restrictions are on.
    if blocks_creations is False or restricts_pushes is False:
        return None

    if pattern:
        special = set("*?[]\\{}")
        if not special.intersection(pattern):
            return None
        namespace, separator, _ = pattern.partition("/")
        if separator and namespace and not special.intersection(namespace):
            return None
        # With only star wildcards, remaining literal text is required for a
        # match. Names avoiding that text remain available. Character classes,
        # escapes, and other pattern operators require separate evaluation.
        if not set("?[]\\{}").intersection(pattern) and pattern.strip("*/"):
            return None

    if blocks_creations is not True or restricts_pushes is not True:
        return "unknown_creation_restriction"
    if pattern in {"*", "**", "**/*"}:
        return "broad_creation_restriction"
    return "unknown_creation_restriction"
