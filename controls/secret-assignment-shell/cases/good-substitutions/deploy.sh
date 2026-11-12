#!/bin/sh
# Every value is fetched at run time; no secret is written here.
pg_password="$(generate_secret)"
PGPASSWORD="$pg_password"
db_password="${DB_PASSWORD}"
export PGPASSWORD db_password
