#!/usr/bin/env bash
# Browser check of the quickstart rows (T097; constitution: each story ends with a local
# visual check). It drives a real browser with chrome-devtools-axi against the demo stack
# (`make dev`, then the frontend dev server on :5173), uploads one licence per row, and saves
# a screenshot of every page at desktop and phone width.
#
# Use:   scripts/browser_check.sh [OUT_DIR]          (default: var/browser-check)
# Needs: chrome-devtools-axi on PATH, and a signed-in session in its browser.
set -uo pipefail  # not -e: "wait" returns non-zero after a timeout, which is not a failure

OUT="${1:-var/browser-check}"
APP="http://127.0.0.1:5173"
export CHROME_DEVTOOLS_AXI_SESSION="${CHROME_DEVTOOLS_AXI_SESSION:-browser-check}"
# One licence per quickstart row: a clean licence, a near expiry, a corroborated expiry, an
# uncertain expiry (the resolver runs) and an injected-text licence.
CASES=(clean_001 near_expiry_001 expired_001 expired_uncertain_001 injected_001)

cd "$(dirname "$0")/.."
mkdir -p "$OUT"
axi() { chrome-devtools-axi "$@"; }
uid() { axi snapshot 2>&1 | grep "$1" | head -1 | grep -o 'uid=[^ ]*' | cut -d= -f2; }

upload() {
  local case_id="$1" data name
  data=$(base64 -w0 "data/generated/$case_id.pdf")
  name=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['applicant_name'])" \
    "evals/cases/synthetic/$case_id.json")
  axi open "$APP/" >/dev/null; axi wait 1500 >/dev/null
  # The file chooser cannot be scripted, so the file is set on the input from page script.
  axi run >/dev/null 2>&1 <<JS
await page.eval(() => {
  const bin = atob("$data"); const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const input = document.querySelector('input[type=file]');
  const dt = new DataTransfer();
  dt.items.add(new File([bytes], "$case_id.pdf", { type: "application/pdf" }));
  input.files = dt.files; input.dispatchEvent(new Event('change', { bubbles: true }));
});
JS
  axi fill "@$(uid 'textbox "Business name')" "$name" >/dev/null
  axi click "@$(uid 'button "Upload"')" >/dev/null; axi wait 8000 >/dev/null
  axi click "@$(uid 'link "Open the run"')" >/dev/null; axi wait 2500 >/dev/null
}

for case_id in "${CASES[@]}"; do
  upload "$case_id"
  run=$(axi eval "() => location.pathname.split('/')[2]" 2>&1 | head -1 | tr -d '\\"' | sed 's/^result: //')
  for size in "1440 900 desktop" "390 844 phone"; do
    read -r width height label <<<"$size"
    axi resize "$width" "$height" >/dev/null 2>&1
    for page in "runs/$run review" "runs/$run/trace trace"; do
      read -r path name <<<"$page"
      axi open "$APP/$path" >/dev/null; axi wait 2500 >/dev/null
      axi screenshot "$OUT/$case_id-$name-$label.png" >/dev/null
    done
  done
  axi resize 1440 900 >/dev/null 2>&1
  echo "ok $case_id"
done
axi open "$APP/runs" >/dev/null; axi wait 2500 >/dev/null; axi screenshot "$OUT/runs.png" >/dev/null
echo "screenshots in $OUT"
