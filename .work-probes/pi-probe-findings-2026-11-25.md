# Pi 1.6.0 discovery and reload observations

Planning evidence for #1896/#1897 and epic #1876. Keep this note and its probe
commits until the P1-A plan record cites durable evidence. This disposable probe
branch is never merged. These are helper-executed host observations, forwarded
as compressed text; this author independently decoded the records, verified the
digests below, and read the RPC responses and fixture TUI captures. This author
did not rerun pi or observe the host directly. Digests identify bytes, not their
author or authenticity. No private session/host names or credential contents are
included here.

## Inputs and provenance

All runs used pi 1.6.0 and throwaway fixture home/agent roots. No owner-session
installation or provider/model turn was requested. Probe subprocesses selected
fixture HOME/config/data/cache/history and a small environment allowlist.
This is configuration separation, not an OS credential boundary or network fence.

| Record | Probe commit or input | SHA256 of decoded supplied record |
|---|---|---|
| Batch 0, isolated version/help | Short shell batch; no committed script | `8d59a9164a3ad5e88157ef12b871ab7db0f3041b3ceddecc10699b97e3481dd9` |
| Batch 1 v1, project assumption refused | `0d6fe2642339974d492a1e12cc556157865e9437`, `pi-discovery.py` | `32d43d067738e1e4d462669a5d4d2876306bee0afefacd5dbfd7fed2a34af944` |
| Batch 1 v2, independent sections | `bdf83ec50a1fdca00de9ff80acd826e961e42ad1`, `pi-discovery.py` | `bb935a8e0188721bc04855ce2a6bb23e49b903b0cc4904491db0777d6a1cb2b1` |
| Batch 2, fixture TUI reload | `bdf83ec50a1fdca00de9ff80acd826e961e42ad1`, `pi-reload.py` | `2d994523f3499eec417fb28c232eaec4172787d70176bbdd173b16f573d9e50f` |

The relative probe paths above are under `.work-probes/`. V2 discovery script
SHA256: `ceb055f0a04d98f6168480eecb4d1b6e433c5ed1d39610ffe953ff8e51ba2c1d`.
Reload script SHA256:
`b23a71fdc5ce8c7eac2c80f93e69d32528085d854d2d4a33acc44d1b3b10d132`.
The supplied records report matching script hashes before execution. Original
decoded records remain outside this publication; this note is a sanitized
summary, not an exact derivative transcript. [Source notes](pi-1.6.0-source-notes.md)
record the matching published-version project-trust contract.

## Paired observations

| Question | Observation and comparison |
|---|---|
| Global discovery | `<agent>/skills/cpp-probe-global/SKILL.md` appeared as a user skill. After removing it, a fresh RPC response omitted it. Its observed `sourceInfo.baseDir` was the agent directory, not the package directory. |
| Metadata location candidate | Adding then removing `<agent>/skills/.cpp-managed/ownership.json` changed neither command rows nor baseline stderr. This tests one hidden layout, not an approved final ledger format. |
| Explicit selection | `--skill` added the unique explicit fixture. `--no-skills --skill` retained it and excluded the automatic global fixture. |
| Project trust | Fresh RPC default `ask`: project skill absent. Synthetic fixture-agent setting `always`: present. Setting `never`: absent. These cwd `.pi/skills` cases used no Git repository; Git initialization was not needed for the trusted positive. |
| Same-name selection | With trust `always`, the project skill won over global. Adding the explicit duplicate retained the project winner; the distinct explicit skill still appeared. Both collision-case stderr records contained the known no-model warning, with no collision warning. This is a bounded observed precedence result. |
| Reload | In a fresh fixture TUI, `/skill` autocomplete showed `cpp-probe-reload`; external removal followed by `/reload` removed that row; restoration followed by `/reload` restored it. The identical input showed the row before and after the absence comparison. No skill was invoked as a model prompt. |
| Cleanup | V1 and v2 recorded fixture absence after undo; batch 2 recorded cleanup and fixture absence. The helper also reported the fixture TUI/process removed. No owner installation was part of these runs. |

V1 exited 1 on its missing-project assertion before later cases ran; it supplies
no metadata-layout or precedence evidence. V2 completed five sections and twelve
RPC cases, each exit 0 without a forced stop. Its result reader's committed
populated response was accepted; empty-success and missing-response controls
were refused locally and in the supplied host self-test record. The global
removal and TUI removal comparisons establish the relevant absence readers can
first observe presence. These observations do not prove every boundary below.

## P1-A design consequences and limits

- Target the documented global user skills root. Report installed fidelity
  separately from contextual effective selection: a current global copy can be
  silently shadowed by a trusted same-name project skill. Surface known bounded
  shadowing; unmeasured runtime context remains effectiveness unknown. Do not
  scan arbitrary projects to manufacture a global effectiveness claim.
- Pi startup initialized fixture-local store files even during offline help,
  according to the supplied batch 0 inspection; their contents were not read.
  Audit copier/verifier zero-credential-probe behavior separately from pi CLI
  initialization. Do not fold both into an unsupported zero-access claim.
- Fixture TUI startup warned `fd not found`, `ripgrep not found`, and no models
  available. Propose informational readiness diagnostics for missing `fd`/`rg`,
  separate from file fidelity and discovery verdicts. Discovery/reload worked;
  these runs do not justify a hard dependency gate or automatic installation.
- No delivered topic copier was exercised. Bundled-reference bytes, expected
  package floor, ownership/adoption safety, syscall confinement, locking,
  concurrency, session-history precedence, B1-B6 controls, provider behavior and
  runtime/container isolation remain implementation/acceptance work. Part 1 is
  not validated by these preparatory fixtures. P1-A coding still awaits #1887
  merge and the applicable plan/publication authorization.
