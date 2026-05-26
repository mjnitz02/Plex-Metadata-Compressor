#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLEX_DATA="${1:-/mnt/user/appdata/plex/Library/Application Support/Plex Media Server}"
IMAGE_NAME="plex-compressor-$(date +%s)"

echo "[plex-compressor] Building Docker image..."
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

echo "[plex-compressor] Compressing Plex data at: $PLEX_DATA"
docker run --rm \
  -v "$PLEX_DATA:/plexdata" \
  "$IMAGE_NAME" \
  /plexdata/Metadata \
  /plexdata/Media/localhost

echo "[plex-compressor] Removing Docker image..."
docker rmi "$IMAGE_NAME" > /dev/null 2>&1 || true

echo "[plex-compressor] Complete."
