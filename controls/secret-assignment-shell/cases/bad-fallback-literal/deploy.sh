#!/bin/sh
# A hardcoded fallback: the default is a literal in the file.
db_password="${DB_PASSWORD:-fallback-literal-9x}"
export db_password
