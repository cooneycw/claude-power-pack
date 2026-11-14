# Direct-file launch inventory control (#1803)

`good-module-only` contains one recorded module launch. `bad-extra-direct-file`
adds a direct `lib/cicd/bootstrap.py` check without adding its row to the same
committed inventory. The real equality helper must reject the bad tree and
accept the good tree. Repairing the inventory in a temporary copy also passes.

The unchanged scanner snapshot from the pre-extension head sees only the
module launch, so it incorrectly accepts the bad tree and agrees on the
module-only good tree. Its bytes also equal the named main artifact; provenance
and the content hash live beside the anchor. The regression failed on the
unextended scanner (one row instead of two) before the implementation changed.

The classifier normalizes a direct checker filename to its corresponding
module/subcommand columns. Bootstrap list remains configuration-only; bootstrap
check retains caller PATH without a CPP uv activation. Opaque filenames,
subcommands or invokers and unsupported argument forms are unresolved rather
than an empty clean inventory. Existing module rows are unchanged.
