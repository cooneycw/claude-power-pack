# ADR 0008 (fixture): a decision record still carrying a census

This tree's census is `controls/census.md`. The tables below are a LEFTOVER copy
that happens to account for every script, including the one the data file does
not. A gate that reads the decision record before the data file scores this
tree clean; the real gate reads the data file and reports it.

## The enumeration

| # | instrument | verdict contract | consumed by | class |
|---|---|---|---|---|
| 1 | `alpha-tool.sh` | `ALPHA: ok` | the fixture gate | G |
| 2 | `beta-tool.sh` | `BETA: ok` | the fixture gate | G |
| 9 | `ruff` | findings | the fixture gate; no file under scripts/ | G |

### Excluded, with the reason

| population | reason under the bound |
|---|---|
| `delta-tool.sh` | a renderer; it emits no verdict |

<!-- instrument-census: external-subjects: ruff -->
