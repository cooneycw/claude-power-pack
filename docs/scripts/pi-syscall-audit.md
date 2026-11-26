# pi-syscall-audit

Classify an explicit JSON record containing an independent operation allowance
and timestamped per-pid `strace -ff -ttt -yy` text. Supply the record as its
positional argument. `--self-test` exercises committed GOOD/BAD/UNKNOWN reader
cases. Exit 0 matches the supplied allowance, 1 reports a forbidden operation,
4 is unexamined/ambiguous input. Neither result claims live host tracing.

The record names skills, primary lock, immutable source, exact settings,
history roots, runtime read roots, metadata-only ancestors, cwd and operation
mode. Optional known aliases describe fixture-controlled path escapes. Every
child must have complete trace framing and its declared exit. Paths resolve
through cwd and annotated descriptors; actual opened descriptor targets are
checked too. Auth metadata/open/read probes, history descendants and outside
writes are findings, including failed probes and transient create/unlink.
Verify admits no writes. Incomplete/resumed syntax, unsupported relevant
syscalls, truncated paths, unresolved descriptors and zero examined operations
are UNKNOWN. A framing-only blind anchor proves the known-bad cases discriminate.

This is a bounded observer, not a kernel policy or runtime credential-isolation
guarantee. Host records must name unsupported syntax and per-case limitations;
one legal install trace does not establish all B1-B6 acceptance rows.

Polling/select/epoll calls inspect their resolved fd targets as metadata; pipe,
socket and anonymous-inode descriptors remain IPC. The reader checks watched
fds at epoll_ctl and the epoll instance at each wait; event data is opaque caller
payload. Unannotated/unresolved descriptors and incomplete fd populations remain
UNKNOWN. Committed Python/Git-shaped GOOD/BAD twins exercise pipe2, multiplexing,
pipe reads/writes, wait4 and complete child framing, including an auth-fd probe.

Additional allowance fields are exact `runtime_files`, readonly
`git_metadata_roots`, and `native_library_dirs` restricted to shared-library
names and the gconv cache. `runtime_reads` contains explicitly derived
interpreter paths. Directory-only readonly opens of the exact lock parent or
source/skills/Git ancestors are metadata capabilities; read/getdents there
still requires a read allowance. Typed fd annotations such as
`3</dev/null<char 1:3>>` are parsed structurally. Discard writes require resolved
`/dev/null` character-device 1:3 identity; creation/truncation or other mutations
never gain that exception. A readonly MAP_SHARED requires matching live
O_RDONLY opener provenance. Clone/dup/close/exec and close-on-exec state update
the fd table; missing provenance stays UNKNOWN, and writable shared maps use
the ordinary write boundary. The committed host-derived composite and sibling
BAD/UNKNOWN cases exercise each extension without asserting full-host coverage.
Exact `runtime_metadata` entries cover interpreter prefix landmarks and their
metadata ancestors only. They authorize no open/read/directory listing or
mutation. An exact prebound timezone target is a `runtime_files` entry; no
general zoneinfo prefix is authorized.
