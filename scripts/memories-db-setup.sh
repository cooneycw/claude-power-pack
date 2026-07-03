#!/usr/bin/env bash
# Provision the CPP common-memory Postgres store on this host (idempotent).
# Intended for a dedicated lab VM (e.g. proxvmmemories15 / 192.168.4.62).
#
# Usage:  sudo bash memories-db-setup.sh <schema.sql> <password-file>
#
# The password file holds ONLY the cpp_memory role password (no newline needed).
# Access is restricted to the LAN + Tailscale CIDRs with scram-sha-256; the
# ledger holds bucket-2 knowledge only (no secrets), so blast radius is low.
set -euo pipefail

SCHEMA_FILE="${1:?schema.sql path required}"
PW_FILE="${2:?password file required}"
DB_NAME="${CPP_MEM_DB:-cpp_memory}"
DB_ROLE="${CPP_MEM_ROLE:-cpp_memory}"
LAN_CIDR="${CPP_MEM_LAN_CIDR:-192.168.0.0/16}"
TS_CIDR="${CPP_MEM_TS_CIDR:-100.64.0.0/10}"

[ "$(id -u)" -eq 0 ] || { echo "ERROR: must run as root"; exit 1; }
[ -f "$SCHEMA_FILE" ] || { echo "ERROR: schema file not found: $SCHEMA_FILE"; exit 1; }
DB_PW="$(cat "$PW_FILE")"
[ -n "$DB_PW" ] || { echo "ERROR: empty password"; exit 1; }

# 1. Install a specific Postgres major (default 17) from the PGDG apt repo.
#    Ubuntu's default repo only carries the LTS-era major, so we add PGDG for
#    anything newer.
PG_MAJOR="${CPP_MEM_PG_MAJOR:-17}"
if ! dpkg -s "postgresql-${PG_MAJOR}" >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates gnupg lsb-release
    install -d /usr/share/postgresql-common/pgdg
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq "postgresql-${PG_MAJOR}"
fi
systemctl enable --now postgresql

PG_VER="${PG_MAJOR}"
PG_CONF="/etc/postgresql/${PG_VER}/main/postgresql.conf"
PG_HBA="/etc/postgresql/${PG_VER}/main/pg_hba.conf"

# 2. Network + auth config (before setting the password, so the hash is scram).
sed -i "s/^#\?listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
sed -i "s/^#\?password_encryption.*/password_encryption = scram-sha-256/" "$PG_CONF"
sed -i "s/^#\?port\s*=.*/port = 5432/" "$PG_CONF"

add_hba_rule() {
    local rule="host    ${DB_NAME}    ${DB_ROLE}    $1    scram-sha-256"
    grep -qF "$rule" "$PG_HBA" || echo "$rule" >> "$PG_HBA"
}
add_hba_rule "127.0.0.1/32"
add_hba_rule "$LAN_CIDR"
add_hba_rule "$TS_CIDR"

systemctl restart postgresql

# 3. Role (idempotent) + password (always reset to the provided one, scram-hashed).
sudo -u postgres psql -v ON_ERROR_STOP=1 -qtA >/dev/null <<SQL
DO \$do\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_ROLE}') THEN
      CREATE ROLE ${DB_ROLE} LOGIN;
   END IF;
END
\$do\$;
ALTER ROLE ${DB_ROLE} WITH LOGIN PASSWORD '${DB_PW}';
SQL

# 4. Database (idempotent).
if ! sudo -u postgres psql -qtA -c "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres createdb -O "${DB_ROLE}" "${DB_NAME}"
fi

# 5. Schema (idempotent) over a local scram connection.
PGPASSWORD="$DB_PW" psql -h 127.0.0.1 -U "$DB_ROLE" -d "$DB_NAME" \
    -v ON_ERROR_STOP=1 -qf "$SCHEMA_FILE"

echo "OK: ${DB_NAME} ready on $(hostname) (postgresql ${PG_VER})"
