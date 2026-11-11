# The instrument census (fixture, data home - issue #1671)

A miniature census in `controls/census.md`, where the real one lives, shaped
exactly like it: a numbered enumeration
table whose column 2 names the instrument, an exclusions section whose column 1
names a population, and an external-subjects declaration.

## The enumeration

| # | instrument | verdict contract | consumed by | class |
|---|---|---|---|---|
| 1 | `alpha-tool.sh` | `ALPHA: ok` | the fixture gate | G |
| 9 | `ruff` | findings | the fixture gate; no file under scripts/ | G |
| 10 | `make verify` as an aggregate | the AND of its prerequisites | the fixture gate | G |

### Excluded, with the reason

| population | reason under the bound |
|---|---|
| `delta-tool.sh` | a renderer; it emits no verdict |

<!-- instrument-census: external-subjects: ruff -->
