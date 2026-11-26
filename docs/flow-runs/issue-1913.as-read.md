<!-- flow-run n=1 id=990a9d5449ea476f882e97f0f1d7e140 -->
## Run 1 - issue #1913 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1913
- Read at:      2026-11-26T05:18:53Z
- updatedAt:    2026-11-26T05:10:06Z   (context only - moves on comments and labels)
- Body digest:  a6fabcbfe04191ab1e0f297d0004a222298cbe96bf276bc8df69e96d3801634f   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1866 of 1866 (cap 16384)

### Body as read
The shipped `scripts/cpp-host-write.sh:277-288` replaces a pre-existing regular destination file with a CPP symlink and returns success. `cmd_link_into` skips symlinks, but every other existing leaf reaches `ln -sf`. A personal `~/.claude/scripts/<helper>` file can therefore lose its bytes during `/cpp:init` Tier 2 or the existing `/cpp:update` Step 5 helper loop.

Observed while implementing #1889 B2a on main base `b1cd1f1635a920ba4839097ebfff8977a0bf7dda`. The helper and maintained callers are unchanged by B2a. This is a live preservation/data-loss problem, so it is filed directly rather than left in the Nit Store. B2a's separate link backend preserves regular replacements; B2b will change update wiring, but cpp:init and direct callers still need the legacy helper corrected.

Reproduced through a disposable Make recipe invoking the actual Bash helper: create a source, create a same-name personal regular destination, assert it is regular and not a symlink, call `bash scripts/cpp-host-write.sh link-into SOURCE DIR NAME`. The command returns 0, the destination becomes a symlink to SOURCE, and the original personal bytes are gone. The owned temporary directory was deleted afterward; no user installation was touched.

Relevant callers: `.claude/commands/cpp/init.md:1274,1300` and `.claude/commands/cpp/update.md:666,716`. Choosing Tier 2 authorizes installing CPP helpers, not replacing an unrelated same-name personal file.

Preserve and refuse unexpected regular files/directories or foreign links. Keep established owned-link behavior explicit, and add a committed known-bad regular-replacement input to the existing helper control plus a real pre-fix regression that fails against this implementation. Ensure native command callers retain the refusal in their actual status/exit handling. Do not broaden #1889 B2a to fix this helper silently.


<!-- end of body -->
