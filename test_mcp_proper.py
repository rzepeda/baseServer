#!/usr/bin/env python3
"""Test MCP protocol with proper SSE session management."""

import asyncio
import json
import httpx


async def test_mcp_protocol():
    """Test MCP protocol with active SSE connection."""
    base_url = "http://localhost:8080"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Start SSE connection
        print("1. Connecting to SSE endpoint...")
        async with client.stream("GET", f"{base_url}/sse", headers={
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }) as response:
            # Read the first event to get session ID
            session_id = None
            async for line in response.aiter_lines():
                print(f"SSE: {line}")
                if "session_id=" in line:
                    session_id = line.split("session_id=")[1].split("&")[0].strip()
                    print(f"\nExtracted session ID: {session_id}\n")
                    break

            if not session_id:
                print("ERROR: Could not get session ID")
                return

            # Now send MCP protocol messages while SSE is still connected
            print("2. Sending tools/list request...")
            tools_response = await client.post(
                f"{base_url}/messages/?session_id={session_id}",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                headers={"Content-Type": "application/json"}
            )
            print(f"tools/list HTTP response: {tools_response.text}")

            # Read SSE response
            print("Reading SSE response for tools/list...")
            event_count = 0
            async for line in response.aiter_lines():
                print(f"SSE: {line}")
                event_count += 1
                if event_count > 10:  # Limit reading
                    break

            print("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(test_mcp_protocol())
