#!/bin/bash
# Test script for MCP server endpoints

BASE_URL="${1:-http://localhost:8080}"

echo "Testing MCP Server at: $BASE_URL"
echo "========================================="

# Test health endpoint
echo -e "\n1. Testing /health endpoint..."
curl -s "$BASE_URL/health" | jq . || echo "Failed"

# Test SSE endpoint (should exist)
echo -e "\n2. Testing /sse endpoint (SSE - should return event-stream)..."
curl -s -N -H "Accept: text/event-stream" "$BASE_URL/sse" | head -n 5

# Test messages endpoint
echo -e "\n3. Testing /messages/ endpoint (MCP JSON-RPC)..."
curl -s -X POST "$BASE_URL/messages/" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .

echo -e "\n========================================="
echo "Testing complete!"
