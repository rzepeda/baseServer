"""Unit tests for minimal MCP server.

These tests validate the basic functionality of the minimal MCP server
implementation used for debugging connection issues.
"""

import json
import re
from typing import Any

import pytest
from starlette.testclient import TestClient

from src.minimal_mcp_server import app, hello


class TestMinimalMCPServer:
    """Test suite for minimal MCP server."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client for the minimal MCP server."""
        return TestClient(app)

    def test_server_initialization(self, client: TestClient) -> None:
        """Test that the minimal server initializes successfully."""
        # Arrange & Act & Assert
        # If the client was created successfully, the server initialized
        assert client is not None
        assert app is not None

    def test_health_endpoint_returns_200(self, client: TestClient) -> None:
        """Test that the health endpoint returns 200 OK."""
        # Arrange & Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["server"] == "minimal-mcp-server"
        assert "version" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_hello_tool_execution(self) -> None:
        """Test that the hello tool returns the expected static response."""
        # Arrange & Act
        result = await hello()

        # Assert
        assert result == "Hello from minimal MCP server!"
        assert isinstance(result, str)

    def test_sse_endpoint_returns_proper_headers(self, client: TestClient) -> None:
        """Test that SSE endpoint returns proper headers for streaming."""
        # Arrange & Act
        with client.stream("GET", "/sse", headers={"Accept": "text/event-stream"}) as response:
            # Assert
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            assert response.headers.get("cache-control") == "no-store"
            assert response.headers.get("x-accel-buffering") == "no"
            # Close stream immediately after checking headers
            response.close()

    def test_sse_endpoint_sends_session_id(self, client: TestClient) -> None:
        """Test that SSE endpoint sends initial event with session_id."""
        # Arrange & Act
        with client.stream("GET", "/sse", headers={"Accept": "text/event-stream"}) as response:
            # Read limited bytes from SSE stream
            data = b""
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > 500 or b"session_id=" in data:  # Stop after getting session_id
                    break

            # Parse the SSE data
            text = data.decode("utf-8")
            session_id = None
            for line in text.split("\n"):
                if line.startswith("data: "):
                    session_id = line[6:]  # Remove "data: " prefix
                    break

            # Assert
            assert session_id is not None
            assert "/messages/" in session_id
            assert "session_id=" in session_id

    def test_messages_endpoint_with_initialize_request(self, client: TestClient) -> None:
        """Test MCP initialize request through /messages endpoint."""
        # Arrange - First get session_id from SSE endpoint
        with client.stream("GET", "/sse", headers={"Accept": "text/event-stream"}) as sse_response:
            data = b""
            for chunk in sse_response.iter_bytes():
                data += chunk
                if len(data) > 500 or b"session_id=" in data:
                    break

            text = data.decode("utf-8")
            session_endpoint = None
            for line in text.split("\n"):
                if line.startswith("data: "):
                    session_endpoint = line[6:]
                    break

        assert session_endpoint is not None
        # Extract session_id from endpoint like "/messages/?session_id=xxx"
        match = re.search(r"session_id=([^&\s]+)", session_endpoint)
        assert match is not None
        session_id = match.group(1)

        # Arrange - Create MCP initialize request
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

        # Act
        response = client.post(
            f"/messages/?session_id={session_id}",
            json=initialize_request,
            headers={"Content-Type": "application/json"},
        )

        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result.get("jsonrpc") == "2.0"
        assert "result" in result or "error" in result

    def test_full_mcp_flow_with_hello_tool(self, client: TestClient) -> None:
        """Test complete MCP flow: connect SSE, initialize, list tools, call hello tool."""
        # Step 1: Connect to SSE and get session_id
        with client.stream("GET", "/sse", headers={"Accept": "text/event-stream"}) as sse_response:
            assert sse_response.status_code == 200
            data = b""
            for chunk in sse_response.iter_bytes():
                data += chunk
                if len(data) > 500 or b"session_id=" in data:
                    break

            text = data.decode("utf-8")
            session_endpoint = None
            for line in text.split("\n"):
                if line.startswith("data: "):
                    session_endpoint = line[6:]
                    break

        assert session_endpoint is not None
        match = re.search(r"session_id=([^&\s]+)", session_endpoint)
        assert match is not None
        session_id = match.group(1)

        # Step 2: Initialize MCP session
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
        init_response = client.post(
            f"/messages/?session_id={session_id}",
            json=initialize_request,
            headers={"Content-Type": "application/json"},
        )
        assert init_response.status_code == 200

        # Step 3: List available tools
        list_tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_response = client.post(
            f"/messages/?session_id={session_id}",
            json=list_tools_request,
            headers={"Content-Type": "application/json"},
        )
        assert tools_response.status_code == 200
        tools_result = tools_response.json()
        assert "result" in tools_result
        tools_list = tools_result["result"].get("tools", [])
        assert len(tools_list) > 0
        # Verify hello tool exists
        hello_tool = next((t for t in tools_list if t["name"] == "hello"), None)
        assert hello_tool is not None

        # Step 4: Call hello tool
        call_tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "hello", "arguments": {}},
        }
        tool_response = client.post(
            f"/messages/?session_id={session_id}",
            json=call_tool_request,
            headers={"Content-Type": "application/json"},
        )
        assert tool_response.status_code == 200
        tool_result = tool_response.json()
        assert "result" in tool_result
        # Verify the hello message is in the response
        content = tool_result["result"].get("content", [])
        assert len(content) > 0
        assert any("Hello from minimal MCP server!" in str(item) for item in content)
