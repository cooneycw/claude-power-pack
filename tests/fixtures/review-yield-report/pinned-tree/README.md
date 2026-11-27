# Pinned receipt input tree (#1925)

`docs/measurements/counter-model/` is a small committed input tree. `tree.json`
records each file's Git blob ID in the original tree-listing order. The test
builds an archive from these bytes without accessing GitHub or repository
history.

`expected.md` was captured from the unchanged `collect_repo` and `render` in
commit fc0624e76f95bb7d332694a6ca4f8e4179c676b3, feeding that tree through its
original per-blob API adapter, an empty merged-PR list and snapshot SHA
`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`. The date interval is
2026-11-11 through 2026-11-20. The archive-backed collector must produce these
same bytes. Filenames deliberately disagree with recording dates; cumulative
snapshots, an independent session, measured kinds and malformed JSON remain
in the population.

`unsafe-names.json` commits malicious archive member names. The tests build
those members literally and require UNKNOWN, rather than extracting anything
or returning an empty successful observation. Missing, unreadable, mismatched,
linked, duplicate and multiple-root archive cases are tested alongside them.
