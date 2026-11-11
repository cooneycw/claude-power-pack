# ADR 0008 (fixture): a decision record that keeps only the rule

This tree's census is `controls/census.md`, and it accounts for the tree
exactly. This record holds no census table at all, which is the shape the real
one has had since issue #1671. A gate that reads the decision record before the
data file parses 0 rows here and refuses a correct tree; the real gate reads the
data file and passes it.

## The enumeration

The enumeration lives in `controls/census.md`.
