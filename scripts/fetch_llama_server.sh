#!/usr/bin/env bash
# Fetch llama.cpp's llama-server (CPU build for Linux x64) into var/llama.cpp, pinned by
# release and SHA-256 (research R10b, ADR-004). Git ignores var/.
# Use: scripts/fetch_llama_server.sh && make local-model
set -euo pipefail
RELEASE="b11985"  # 2026-10-29: at least two weeks old when pinned, like every other pin
SHA256="7bed5fe6c601caf7a063029170fc83e1425dcc19278925512e4edba4fc88fb44"
ASSET="llama-${RELEASE}-bin-ubuntu-x64.tar.gz"
DEST="${1:-var/llama.cpp}"
URL="https://github.com/ggml-org/llama.cpp/releases/download/${RELEASE}/${ASSET}"

mkdir -p "$DEST"
archive="$DEST/$ASSET"
if [[ -f "$archive" ]] && echo "$SHA256  $archive" | sha256sum -c --status; then
  echo "ok $ASSET (cached)"
else
  curl -fsSL --max-time 600 -o "$archive.tmp" "$URL"
  echo "$SHA256  $archive.tmp" | sha256sum -c --status \
    || { echo "checksum mismatch for $ASSET: the download is not the pinned release" >&2; rm -f "$archive.tmp"; exit 1; }
  mv "$archive.tmp" "$archive"
  echo "ok $ASSET"
fi
tar -xzf "$archive" -C "$DEST"
server="$(find "$DEST" -name llama-server -type f | head -1)"
[[ -n "$server" ]] || { echo "llama-server not found in $ASSET" >&2; exit 1; }
ln -sf "$(realpath "$server")" "$DEST/llama-server"
echo "llama-server is at $DEST/llama-server"
