#!/usr/bin/env bash
# xspec E2E: start the real Python backend and verify /health.
#
# SPEC S1 (live): Server health endpoint
#   Given the Python backend is started on port 8080
#   When curl sends GET /health
#   Then response is 200 {"status":"ok"}
#   And CORS header allows tauri://localhost
#
# SPEC S5 (live): Seed data accessible through live server
#   When the server is running with seed data
#   Then einstein/666666 can login and pool returns articles
#
# Cross-platform: macOS (BSD) and Linux (GNU).
#
# Usage:
#   bash backend/tests/integration/test_health_e2e.sh
#   PORT=8081 bash backend/tests/integration/test_health_e2e.sh
set -euo pipefail

PORT="${PORT:-8080}"
HOST="127.0.0.1"
BASE="http://${HOST}:${PORT}"
PY=python3
PASS=0
FAIL=0

cleanup() {
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✓ $label"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $label"
    echo "    expected: $expected"
    echo "    actual:   $actual"
    FAIL=$((FAIL + 1))
  fi
}

# ── Start server ────────────────────────────────────────────────────────

echo "=== Starting backend on ${BASE} ==="
ROOT=$(git -C "$(dirname "$0")/../../.." rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT"
.venv/bin/python -m uvicorn peerpedia_api.main:app --host "$HOST" --port "$PORT" &
SERVER_PID=$!

for i in $(seq 1 30); do
  if curl -s "${BASE}/health" >/dev/null 2>&1; then
    echo "Server ready after ${i}s"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Server failed to start within 30s"
    exit 1
  fi
  sleep 0.5
done

# ── SPEC S1: Health endpoint ────────────────────────────────────────────

echo ""
echo "=== SPEC S1: Health endpoint ==="
STATUS=$(curl -s "${BASE}/health" | $PY -c "import sys,json; print(json.load(sys.stdin)['status'])")
assert_eq "health returns ok" "ok" "$STATUS"

HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/health")
assert_eq "health returns HTTP 200" "200" "$HTTP_CODE"

# ── SPEC S1: CORS ───────────────────────────────────────────────────────

echo ""
echo "=== SPEC S1: CORS headers ==="
CORS_ORIGIN=$(curl -s -H "Origin: tauri://localhost" -D - "${BASE}/health" 2>/dev/null \
  | grep -i 'access-control-allow-origin' | tr -d '\r' | awk '{print $2}')
assert_eq "CORS allows tauri://localhost" "tauri://localhost" "$CORS_ORIGIN"

# ── SPEC S5: Login ─────────────────────────────────────────────────────

echo ""
echo "=== SPEC S5: Seed user login ==="
LOGIN=$(curl -s -X POST "${BASE}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"einstein","password":"666666"}')
TOKEN=$(echo "$LOGIN" | $PY -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
USER=$(echo "$LOGIN" | $PY -c "import sys,json; print(json.load(sys.stdin)['user']['username'])")

if [ -n "$TOKEN" ]; then
  echo "  ✓ login returns token"
  PASS=$((PASS + 1))
else
  echo "  ✗ login failed: $LOGIN"
  FAIL=$((FAIL + 1))
fi
assert_eq "login returns einstein" "einstein" "$USER"

# ── SPEC S5: Pool ──────────────────────────────────────────────────────

echo ""
echo "=== SPEC S5: Pool endpoint ==="
POOL=$(curl -s "${BASE}/api/v1/pool" -H "Authorization: Bearer ${TOKEN}")
COUNT=$(echo "$POOL" | $PY -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('articles',[])))")

if [ "$COUNT" -gt 0 ] 2>/dev/null; then
  echo "  ✓ pool has ${COUNT} articles"
  PASS=$((PASS + 1))
else
  echo "  ✗ pool returned ${COUNT} articles"
  FAIL=$((FAIL + 1))
fi

# ── Summary ─────────────────────────────────────────────────────────────

echo ""
echo "========================================="
echo "  E2E: ${PASS} passed, ${FAIL} failed"
echo "========================================="

[ "$FAIL" -eq 0 ] || exit 1
