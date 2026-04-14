#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:7799"

echo "=== Smoke Testing Chatty Server ==="

# Health check
echo -n "Health check... "
curl -sf "$BASE/health" | grep -q "ok" && echo "OK" || (echo "FAIL" && exit 1)

# Register user
echo -n "Register user... "
RESP=$(curl -sf -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"smoke@test.com","nickname":"smoketest","password":"password123"}')
echo "OK (id=$(echo $RESP | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])'))"

# Login
echo -n "Login... "
TOKEN=$(curl -sf -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"smoke@test.com","password":"password123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
echo "OK"

# Create room
echo -n "Create room... "
ROOM=$(curl -sf -X POST "$BASE/rooms" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"Smoke Test Room"}')
ROOM_ID=$(echo $ROOM | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
echo "OK (id=$ROOM_ID)"

# Send message
echo -n "Send message... "
curl -sf -X POST "$BASE/rooms/$ROOM_ID/messages" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"text":"Hello World!"}' | grep -q "Hello World" && echo "OK" || (echo "FAIL" && exit 1)

echo ""
echo "All smoke tests passed!"
