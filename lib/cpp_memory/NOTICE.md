# Third-party image attribution (common-memory store)

The pluggable common-memory store (issue #472) uses the official PostgreSQL
Docker image for the two Postgres tiers only:

- **Tier ii (local-pg)** - `lib/cpp_memory/docker-compose.yml`
- **Tier iii (remote-pg)** - provisioned by `scripts/memories-db-setup.sh`

**Tier i (md)** uses no container and no third-party image (pure local markdown).

## PostgreSQL (`postgres:17`)

- Image: `postgres:17` (a Docker Official Image), digest-pinned in
  `lib/cpp_memory/docker-compose.yml`.
- Upstream: <https://hub.docker.com/_/postgres> / <https://www.postgresql.org/>
- License: **The PostgreSQL License** - a permissive, OSI-approved,
  BSD/MIT-style licence. See <https://www.postgresql.org/about/licence/>.

CPP does not vendor, modify, or redistribute this image; it is pulled from the
registry at run time by whoever opts into tier ii/iii. This file is attribution
only and imposes no obligation on CPP users beyond the upstream licence.
