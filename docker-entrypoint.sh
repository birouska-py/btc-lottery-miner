#!/bin/sh
# Ajusta o dono do volume persistente e derruba privilégios para o usuário "miner".
set -eu

DATA_DIR="${LOTTERY_DATA_DIR:-/app/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown -R miner:miner "$DATA_DIR" 2>/dev/null || true
  exec gosu miner "$@"
fi

exec "$@"
