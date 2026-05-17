#!/usr/bin/env bash
# Real-mode helper (mirrors SshProvisioner.deploy). Run ON the agent VPS.
# Usage: deploy-agent.sh <slot_dir>   (expects docker-compose.yml + root-only .env)
set -euo pipefail
SLOT_DIR="${1:?usage: deploy-agent.sh <slot_dir>}"
test -f "$SLOT_DIR/docker-compose.yml" || { echo "no compose in $SLOT_DIR" >&2; exit 1; }
test -f "$SLOT_DIR/.env" && chmod 600 "$SLOT_DIR/.env"
mkdir -p "$SLOT_DIR/data" "$SLOT_DIR/workspaces"
cd "$SLOT_DIR" && docker compose up -d
