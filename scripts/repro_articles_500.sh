#!/usr/bin/env bash
# Reproduction script: test GET /api/v1/articles under various conditions
# Usage: bash scripts/repro_articles_500.sh
set -euo pipefail

BASE="http://localhost:8080"
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass=0
fail=0

check() {
  local desc="$1" url="$2" expected="${3:-2}"
  local code resp_file
  resp_file=$(mktemp)
  code=$(curl -s -o "$resp_file" -w "%{http_code}" -H "Origin: http://localhost:5173" "$BASE$url" 2>/dev/null || echo "000")
  if [[ "$code" =~ ^[$expected] ]]; then
    echo -e "${GREEN}PASS${NC} [$code] $desc"
    ((pass++)) || true
  else
    echo -e "${RED}FAIL${NC} [$code] $desc"
    echo "  Body: $(head -c 200 "$resp_file")"
    ((fail++)) || true
  fi
  rm -f "$resp_file"
}

check_auth() {
  local desc="$1" url="$2" token="$3" expected="${4:-2}"
  local code resp_file
  resp_file=$(mktemp)
  code=$(curl -s -o "$resp_file" -w "%{http_code}" \
    -H "Origin: http://localhost:5173" \
    -H "Authorization: Bearer $token" \
    "$BASE$url" 2>/dev/null || echo "000")
  if [[ "$code" =~ ^[$expected] ]]; then
    echo -e "${GREEN}PASS${NC} [$code] $desc"
    ((pass++)) || true
  else
    echo -e "${RED}FAIL${NC} [$code] $desc"
    echo "  Body: $(head -c 200 "$resp_file")"
    ((fail++)) || true
  fi
  rm -f "$resp_file"
}

echo "=== Reproduction run at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo ""

# ── Basic sanity ──
echo "── Basic sanity ──"
check "GET /health" "/health"
check "GET /articles (no auth)" "/api/v1/articles"
check "GET /articles?page=1&size=5" "/api/v1/articles?page=1&size=5"
check "GET /articles?status=draft" "/api/v1/articles?status=draft"
check "GET /articles?status=sedimentation" "/api/v1/articles?status=sedimentation"

# ── With auth tokens ──
echo ""
echo "── With auth tokens ──"
check "GET /articles (JWT for nonexistent user)" "/api/v1/articles" "2"

# Try to get a valid token
echo -n "  Getting valid token... "
LOGIN_RESP=$(curl -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{"username":"12321","password":"test123"}' 2>/dev/null)
VALID_TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")
USER_ID=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('user',{}).get('id',''))" 2>/dev/null || echo "")

if [ -n "$VALID_TOKEN" ] && [ "$VALID_TOKEN" != "" ]; then
  echo "OK"
  check_auth "GET /articles (valid auth)" "/api/v1/articles" "$VALID_TOKEN"
  if [ -n "$USER_ID" ] && [ "$USER_ID" != "" ]; then
    check_auth "GET /articles?author_id=$USER_ID" "/api/v1/articles?author_id=$USER_ID" "$VALID_TOKEN"
  fi
else
  echo "SKIPPED (could not get valid token)"
fi

# ── Edge cases ──
echo ""
echo "── Edge cases ──"
check "GET /articles?page=99999" "/api/v1/articles?page=99999"
check "GET /articles?page=0" "/api/v1/articles?page=0"
check "GET /articles?author_id=does-not-exist" "/api/v1/articles?author_id=does-not-exist"

# ── Concurrent requests ──
echo ""
echo "── Concurrent requests (5 parallel) ──"
tmpdir=$(mktemp -d)
pids=()
for i in 1 2 3 4 5; do
  (
    curl -s -o /dev/null -w "%{http_code}" \
      -H "Origin: http://localhost:5173" \
      "$BASE/api/v1/articles?page=$i" 2>/dev/null || echo "000"
  ) > "$tmpdir/req$i.txt" &
  pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
concurrent_fail=0
for i in 1 2 3 4 5; do
  code=$(cat "$tmpdir/req$i.txt" 2>/dev/null || echo "000")
  if [[ ! "$code" =~ ^[2] ]]; then
    echo -e "  ${RED}FAIL${NC} request $i got HTTP $code"
    concurrent_fail=1
  fi
done
if [ "$concurrent_fail" -eq 0 ]; then
  echo -e "${GREEN}PASS${NC} All 5 concurrent requests returned 2xx"
  ((pass++)) || true
else
  ((fail++)) || true
fi
rm -rf "$tmpdir"

# ── Results ──
echo ""
echo "=== Results: $pass passed, $fail failed ==="

# Show recent backend errors
echo ""
echo "── Recent backend log (last 15 lines) ──"
tail -15 /Users/chenqimeng/Projects/peerpedia/backend/logs/backend.log 2>/dev/null || echo "(no log file)"

exit $fail
