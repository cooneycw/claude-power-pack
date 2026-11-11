# `memories-db-setup` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `memories-db-setup`

- memories-db-setup - provisions the CPP common-memory Postgres store on a host, idempotently; intended for a dedicated lab VM. Run as root with a schema file and a password file holding only the `cpp_memory` role password. Access is restricted to the LAN and Tailscale CIDRs with scram-sha-256; the ledger holds bucket-2 knowledge only and no secrets, which is what keeps the blast radius low
