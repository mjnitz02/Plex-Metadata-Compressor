#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METADATA_PATH="${1:-/mnt/user/appdata/plex/Library/Application Support/Plex Media Server/Metadata}"
IMAGE_NAME="plex-compressor-$(date +%s)"

echo "[plex-compressor] Building Docker image..."
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

echo "[plex-compressor] Compressing metadata at: $METADATA_PATH"
docker run --rm \
  -v "$METADATA_PATH:/metadata" \
  "$IMAGE_NAME" /metadata

echo "[plex-compressor] Removing Docker image..."
docker rmi "$IMAGE_NAME" > /dev/null 2>&1 || true

echo "[plex-compressor] Complete."
