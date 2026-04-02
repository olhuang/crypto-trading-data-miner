#!/usr/bin/env bash
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-crypto_trading_postgres}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-crypto_trading}"

cat db/verify/phase_1_verification.sql | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"
