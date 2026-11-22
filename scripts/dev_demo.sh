#!/usr/bin/env bash
# Local demo: backend in label-demo mode (no model key needed) on :8000.
# Creates throwaway secrets and a demo reviewer in var/demo/ (gitignored) on first run.
# Run the frontend separately with: cd frontend && npm run dev   (proxies /api to :8000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/var/demo"
ENV_FILE="$DEMO/.env"
mkdir -p "$DEMO"
if [[ ! -f "$ENV_FILE" ]]; then
  PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
  uv --project "$ROOT/backend" run python - "$ENV_FILE" "$PASSWORD" <<'PY'
import json, secrets, sys
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
path, password = sys.argv[1], sys.argv[2]
lines = {
    "FERNET_KEYS": Fernet.generate_key().decode(),
    "SESSION_SECRET": secrets.token_hex(32),
    "REVIEWER_ACCOUNTS": json.dumps({"demo": PasswordHasher().hash(password)}),
    "COOKIE_SECURE": "false",
}
with open(path, "w") as f:
    f.writelines(f"{k}='{v}'\n" for k, v in lines.items())
PY
  echo "demo reviewer: user 'demo', password '$PASSWORD' (shown once; saved nowhere else)"
fi
set -a; source "$ENV_FILE"; set +a
# The synthetic catalogue is generated for a fixed "today" (test-cases.md); the demo uses it too.
export DATA_DIR="$DEMO/data" DEMO_ANSWERS_DIR="$ROOT/evals/cases/synthetic" DEMO_TODAY=2026-06-01 TESSDATA_PREFIX="$ROOT/var/tessdata"
cd "$ROOT/backend"
exec uv run uvicorn licence_kyb.api.main:app --host 127.0.0.1 --port 8000
