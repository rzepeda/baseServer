#!/bin/bash
# Test complete MCP protocol flow

echo "=== Testing MCP Protocol Flow ==="
echo ""

# Step 1: Connect to SSE and get session ID
echo "1. Connecting to SSE endpoint to get session ID..."
SESSION_RESPONSE=$(timeout 2 curl -s -N -H "Accept: text/event-stream" http://localhost:8080/sse 2>&1 | head -n 2)
echo "$SESSION_RESPONSE"

# Extract session ID from response
SESSION_ID=$(echo "$SESSION_RESPONSE" | grep "session_id" | sed 's/.*session_id=\([^&]*\).*/\1/')
echo ""
echo "Extracted session ID: $SESSION_ID"
echo ""

# Step 2: Test tools/list with session ID
if [ -n "$SESSION_ID" ]; then
    echo "2. Testing tools/list with session ID..."
    curl -s -X POST "http://localhost:8080/messages/?session_id=$SESSION_ID" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .
    echo ""

    # Step 3: Test tools/call with session ID
    echo "3. Testing tools/call (get_youtube_transcript)..."
    curl -s -X POST "http://localhost:8080/messages/?session_id=$SESSION_ID" \
      -H "Content-Type: application/json" \
      -d '{
        "jsonrpc":"2.0",
        "id":2,
        "method":"tools/call",
        "params":{
          "name":"get_youtube_transcript",
          "arguments":{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        }
      }' | jq .
else
    echo "ERROR: Could not get session ID from SSE endpoint"
fi
