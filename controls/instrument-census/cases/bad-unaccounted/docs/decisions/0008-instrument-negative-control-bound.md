# ADR 0008 (fixture): what an instrument is, and when it needs a negative control

A miniature census, shaped exactly like the real one: a numbered enumeration
table whose column 2 names the instrument, an exclusions section whose column 1
names a population, and an external-subjects declaration.

## The enumeration

| # | instrument | verdict contract | consumed by | class |
|---|---|---|---|---|
| 1 | `alpha-tool.sh` | `ALPHA: ok` | the fixture gate | G |
| 9 | `ruff` | findings | the fixture gate; no file under scripts/ | G |

### Excluded, with the reason

| population | reason under the bound |
|---|---|
| `delta-tool.sh` | a renderer; it emits no verdict |

<!-- instrument-census: external-subjects: ruff -->

## Notes

Row 1's gate runs before `beta-tool.sh` and after nothing else. That
sentence is this case: `beta-tool.sh` is NAMED in the document's prose
and accounted for by neither table, so an extractor reading every
backticked token anywhere in the file scores the tree clean while the
column-scoped rule reports it. Nothing else here is a finding.
