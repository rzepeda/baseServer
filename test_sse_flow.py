#!/usr/bin/env python3
"""Test the complete MCP SSE flow: POST to /messages and receive response via SSE stream."""
import asyncio
import json
import sys
from typing import Any

import httpx


async def test_mcp_sse_flow(base_url: str) -> None:
    """Test the complete MCP SSE flow."""
    print(f"\n{'='*60}")
    print("MCP SSE FLOW TEST")
    print(f"{'='*60}")
    print(f"Testing: {base_url}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Connect to SSE endpoint and get session_id
        print("[STEP 1] Connecting to SSE endpoint...")
        async with client.stream("GET", f"{base_url}/sse",
                                 headers={"Accept": "text/event-stream"}) as response:
            print(f"  Status: {response.status_code}")

            # Read first SSE event to get session_id
            session_id = None
            async for line in response.aiter_lines():
                print(f"  SSE: {line}")
                if line.startswith("data: /messages/"):
                    # Extract session_id from data line
                    session_id = line.split("session_id=")[1]
                    print(f"  ✓ Session ID: {session_id}\n")
                    break

            if not session_id:
                print("  ✗ Failed to get session_id")
                return

            # Step 2: In parallel, listen to SSE stream and send initialize request
            print("[STEP 2] Sending initialize request via /messages endpoint...")

            # Create initialize request
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            }

            # Send POST to /messages (this will return 202)
            messages_url = f"{base_url}/messages/?session_id={session_id}"
            post_response = await client.post(
                messages_url,
                json=initialize_request,
                headers={"Content-Type": "application/json"},
            )
            print(f"  POST Status: {post_response.status_code}")
            print(f"  POST Response: {post_response.text}\n")

            # Step 3: Listen to SSE stream for the JSON-RPC response
            print("[STEP 3] Listening to SSE stream for initialize response...")
            response_received = False
            event_count = 0

            async for line in response.aiter_lines():
                event_count += 1
                print(f"  SSE [{event_count}]: {line[:200]}")  # Limit output length

                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)
                        if isinstance(data, dict) and "jsonrpc" in data:
                            print(f"\n  ✓ Received JSON-RPC response:")
                            print(f"    {json.dumps(data, indent=2)}")
                            response_received = True
                            break
                    except json.JSONDecodeError:
                        pass

                # Safety limit
                if event_count > 20:
                    print("\n  ⚠ Reached event limit (20)")
                    break

            if not response_received:
                print("\n  ✗ No JSON-RPC response received via SSE")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    asyncio.run(test_mcp_sse_flow(base_url))
