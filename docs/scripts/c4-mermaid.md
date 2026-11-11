# `c4-mermaid` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `c4-mermaid`

- c4-mermaid - the rendering engine behind `/documentation:c4` (#411), a zero-dependency pure-Python replacement for the removed `nano-banana` MCP server. L1-L3 are emitted as Mermaid `flowchart` diagrams with `subgraph` boundaries and `classDef` C4 colours, and L4 as a `classDiagram` - both chosen because they render inline on GitHub, unlike the Mermaid C4 extension, which GitHub does not bundle and shows as raw text. It also restores the edge-validity QA gate the old renderer provided: every edge endpoint must reference a defined node, and dense diagrams are flagged for splitting. Input is a JSON C4 model, output one `.mmd` per level plus `index.md` and `c4-manifest.json`
