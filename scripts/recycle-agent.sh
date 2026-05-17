#!/usr/bin/env bash
# Real-mode helper (mirrors SshProvisioner.recycle). Stops the container and wipes
# ALL tenant data — nothing survives recycling (ToS §4 / D12).
# Usage: recycle-agent.sh <slot_dir>
set -euo pipefail
SLOT_DIR="${1:?usage: recycle-agent.sh <slot_dir>}"
if [ -f "$SLOT_DIR/docker-compose.yml" ]; then
  (cd "$SLOT_DIR" && docker compose down -v) || true
fi
rm -rf "$SLOT_DIR/data" "$SLOT_DIR/workspaces" "$SLOT_DIR/.env"
