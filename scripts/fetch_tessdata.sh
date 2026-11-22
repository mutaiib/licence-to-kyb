#!/usr/bin/env bash
# Fetch Tesseract language data (eng, ara) into var/tessdata, pinned by SHA-256 (research R9a).
# Use: scripts/fetch_tessdata.sh && export TESSDATA_PREFIX="$PWD/var/tessdata"
set -euo pipefail
DEST="${1:-var/tessdata}"
BASE="https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0"
mkdir -p "$DEST"
fetch() {
  local lang="$1" sha="$2" file="$DEST/$1.traineddata"
  if [[ -f "$file" ]] && echo "$sha  $file" | sha256sum -c --status; then echo "ok $lang (cached)"; return; fi
  curl -fsSL --max-time 120 -o "$file.tmp" "$BASE/$lang.traineddata"
  if [[ "$sha" != "PIN_ON_FIRST_FETCH" ]]; then
    echo "$sha  $file.tmp" | sha256sum -c --status || { echo "checksum mismatch for $lang" >&2; rm -f "$file.tmp"; exit 1; }
  fi
  mv "$file.tmp" "$file"
  echo "ok $lang $(sha256sum "$file" | cut -d' ' -f1)"
}
fetch eng 7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2
fetch ara e3206d3dc87fd50c24a0fb9f01838615911d25168f4e64415244b67d2bb3e729
