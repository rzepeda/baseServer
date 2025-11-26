#!/usr/bin/env python3
"""Test script to validate MCP endpoints like Claude.ai would connect.

This script makes real HTTP requests to test the MCP server endpoints,
simulating how Claude.ai's MCP client would interact with the server.

Usage:
    # Test local server
    python test_mcp_endpoints.py http://localhost:8080

    # Test through Cloudflare tunnel
    python test_mcp_endpoints.py https://your-tunnel-url.trycloudflare.com
"""

import json
import re
import sys
import threading
import time
from typing import Any

import httpx


def test_health_endpoint(base_url: str) -> bool:
    """Test the /health endpoint."""
    print("\n[TEST] Health Endpoint")
    print(f"  URL: {base_url}/health")

    try:
        response = httpx.get(f"{base_url}/health", timeout=10.0)
        print(f"  Status: {response.status_code}")
        print(f"  Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            assert data["status"] == "healthy"
            print("  ✓ PASSED")
            return True
        else:
            print(f"  ✗ FAILED - Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ FAILED - {type(e).__name__}: {e}")
        return False


def test_sse_endpoint(base_url: str) -> str | None:
    """Test the /sse endpoint and extract session_id."""
    print("\n[TEST] SSE Endpoint - Connection")
    print(f"  URL: {base_url}/sse")

    try:
        with httpx.stream(
            "GET",
            f"{base_url}/sse",
            headers={"Accept": "text/event-stream"},
            timeout=10.0,
        ) as response:
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('content-type')}")

            if response.status_code != 200:
                print(f"  ✗ FAILED - Expected 200, got {response.status_code}")
                return None

            if "text/event-stream" not in response.headers.get("content-type", ""):
                print("  ✗ FAILED - Wrong content-type")
                return None

            # Read first chunk to get session_id
            print("  Reading SSE stream...")
            data = b""
            for chunk in response.iter_bytes():
                data += chunk
                if b"session_id=" in data:
                    break
                if len(data) > 1000:  # Safety limit
                    break

            text = data.decode("utf-8")
            print(f"  Received data: {text[:200]}...")

            # Parse session_id from SSE data
            session_endpoint = None
            for line in text.split("\n"):
                if line.startswith("data: "):
                    session_endpoint = line[6:].strip()
                    break

            if not session_endpoint:
                print("  ✗ FAILED - No session endpoint found in SSE stream")
                return None

            match = re.search(r"session_id=([^&\s]+)", session_endpoint)
            if not match:
                print(f"  ✗ FAILED - Could not extract session_id from: {session_endpoint}")
                return None

            session_id = match.group(1)
            print(f"  Session ID: {session_id}")
            print("  ✓ PASSED")
            return session_id

    except Exception as e:
        print(f"  ✗ FAILED - {type(e).__name__}: {e}")
        return None


def test_initialize(base_url: str, session_id: str) -> bool:
    """Test MCP initialize request."""
    print("\n[TEST] MCP Initialize")
    print(f"  URL: {base_url}/messages/?session_id={session_id}")

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

    try:
        response = httpx.post(
            f"{base_url}/messages/?session_id={session_id}",
            json=initialize_request,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"  Response: {json.dumps(result, indent=2)}")
            if "result" in result or "error" in result:
                print("  ✓ PASSED")
                return True
            else:
                print("  ✗ FAILED - Invalid JSON-RPC response")
                return False
        else:
            print(f"  ✗ FAILED - Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"  ✗ FAILED - {type(e).__name__}: {e}")
        return False


def test_list_tools(base_url: str, session_id: str) -> bool:
    """Test MCP tools/list request."""
    print("\n[TEST] List Tools")
    print(f"  URL: {base_url}/messages/?session_id={session_id}")

    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    try:
        response = httpx.post(
            f"{base_url}/messages/?session_id={session_id}",
            json=list_tools_request,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"  Response: {json.dumps(result, indent=2)}")

            if "result" in result:
                tools = result["result"].get("tools", [])
                print(f"  Found {len(tools)} tools")
                for tool in tools:
                    print(f"    - {tool.get('name')}: {tool.get('description')}")

                # Check for hello tool
                hello_tool = next((t for t in tools if t["name"] == "hello"), None)
                if hello_tool:
                    print("  ✓ PASSED - Found 'hello' tool")
                    return True
                else:
                    print("  ✗ FAILED - 'hello' tool not found")
                    return False
            else:
                print("  ✗ FAILED - No 'result' in response")
                return False
        else:
            print(f"  ✗ FAILED - Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"  ✗ FAILED - {type(e).__name__}: {e}")
        return False


def test_call_hello_tool(base_url: str, session_id: str) -> bool:
    """Test calling the hello tool."""
    print("\n[TEST] Call Hello Tool")
    print(f"  URL: {base_url}/messages/?session_id={session_id}")

    call_tool_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "hello", "arguments": {}},
    }

    try:
        response = httpx.post(
            f"{base_url}/messages/?session_id={session_id}",
            json=call_tool_request,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"  Response: {json.dumps(result, indent=2)}")

            if "result" in result:
                content = result["result"].get("content", [])
                if any("Hello from minimal MCP server!" in str(item) for item in content):
                    print("  ✓ PASSED - Got expected greeting")
                    return True
                else:
                    print(f"  ✗ FAILED - Unexpected content: {content}")
                    return False
            else:
                print("  ✗ FAILED - No 'result' in response")
                return False
        else:
            print(f"  ✗ FAILED - Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"  ✗ FAILED - {type(e).__name__}: {e}")
        return False


def main() -> None:
    """Run all tests."""
    if len(sys.argv) < 2:
        print("Usage: python test_mcp_endpoints.py <base_url>")
        print("Example: python test_mcp_endpoints.py http://localhost:8080")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")

    print("=" * 60)
    print("MCP ENDPOINT TEST SUITE")
    print("=" * 60)
    print(f"Testing: {base_url}")

    results = {}

    # Test 1: Health endpoint
    results["health"] = test_health_endpoint(base_url)

    # Test 2: SSE endpoint
    session_id = test_sse_endpoint(base_url)
    results["sse"] = session_id is not None

    if not session_id:
        print("\n" + "=" * 60)
        print("ABORTING - Cannot proceed without session_id")
        print("=" * 60)
        sys.exit(1)

    # Test 3: Initialize
    results["initialize"] = test_initialize(base_url, session_id)

    # Test 4: List tools
    results["list_tools"] = test_list_tools(base_url, session_id)

    # Test 5: Call hello tool
    results["call_hello"] = test_call_hello_tool(base_url, session_id)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name:20s} {status}")

    total = len(results)
    passed = sum(1 for p in results.values() if p)
    print(f"\nTotal: {passed}/{total} passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("The MCP server is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        print("The MCP server has issues that need to be fixed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
