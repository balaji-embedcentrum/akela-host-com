#!/usr/bin/env bash
# Real-mode helper: wipe a slot's workspace + agent home WITHOUT touching the
# container (used by admin "wipe data"). Usage: wipe-data.sh <slot_dir>
set -euo pipefail
SLOT_DIR="${1:?usage: wipe-data.sh <slot_dir>}"
rm -rf "$SLOT_DIR/data" "$SLOT_DIR/workspaces"
mkdir -p "$SLOT_DIR/data" "$SLOT_DIR/workspaces"
