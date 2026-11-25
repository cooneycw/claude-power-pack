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
