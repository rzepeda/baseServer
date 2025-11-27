"""
Claude.ai MCP Connector Emulator
This emulates exactly what Claude.ai does when connecting to a remote MCP server.
Run this to see the exact errors that Claude.ai is receiving.
"""

import httpx
import asyncio
import json
from datetime import datetime

# ANSI color codes for terminal output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

async def test_mcp_connection(server_url: str):
    """Emulate Claude.ai's connection to an MCP server."""
    
    print(f"{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}Claude.ai MCP Connector Emulator{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")
    print(f"Testing connection to: {server_url}\n")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        
        # Test 1: Initialize connection (what Claude.ai does first)
        print(f"{YELLOW}[Test 1/4] Sending 'initialize' request...{RESET}")
        print(f"This is the first thing Claude.ai does when connecting.\n")
        
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "claude-desktop",
                    "version": "1.0.0"
                }
            }
        }
        
        try:
            response = await client.post(
                server_url,
                json=initialize_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*",  # Claude.ai sends this!
                    "User-Agent": "Claude-Desktop/1.0"
                }
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}\n")
            
            if response.status_code == 200:
                print(f"{GREEN}✓ Initialize request successful!{RESET}")
                
                # Parse response
                content = response.text
                print(f"\nRaw response:\n{content[:500]}...\n")
                
                # Check if it's SSE format
                if content.startswith("event:"):
                    print(f"{YELLOW}⚠ Response is in SSE format{RESET}")
                    # Extract JSON from SSE
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            json_str = line[6:]
                            try:
                                data = json.loads(json_str)
                                print(f"\nParsed JSON:\n{json.dumps(data, indent=2)}\n")
                                
                                if 'result' in data:
                                    print(f"{GREEN}✓ Server returned valid initialization result{RESET}")
                                    server_info = data.get('result', {}).get('serverInfo', {})
                                    print(f"Server: {server_info.get('name')} v{server_info.get('version')}")
                                elif 'error' in data:
                                    print(f"{RED}✗ Server returned error:{RESET}")
                                    print(f"  {data['error']}")
                                    
                            except json.JSONDecodeError as e:
                                print(f"{RED}✗ Failed to parse JSON: {e}{RESET}")
                else:
                    # Try to parse as JSON
                    try:
                        data = json.loads(content)
                        print(f"\nParsed JSON:\n{json.dumps(data, indent=2)}\n")
                        
                        if 'result' in data:
                            print(f"{GREEN}✓ Server returned valid initialization result{RESET}")
                        elif 'error' in data:
                            print(f"{RED}✗ Server returned error:{RESET}")
                            print(f"  {data['error']}")
                    except json.JSONDecodeError as e:
                        print(f"{RED}✗ Response is not valid JSON: {e}{RESET}")
            else:
                print(f"{RED}✗ Initialize request failed!{RESET}")
                print(f"Response: {response.text}\n")
                return False
                
        except httpx.TimeoutException:
            print(f"{RED}✗ Request timed out after 30 seconds{RESET}\n")
            return False
        except httpx.ConnectError as e:
            print(f"{RED}✗ Connection error: {e}{RESET}\n")
            return False
        except Exception as e:
            print(f"{RED}✗ Unexpected error: {e}{RESET}\n")
            return False
        
        # Test 2: Send initialized notification
        print(f"\n{YELLOW}[Test 2/4] Sending 'notifications/initialized'...{RESET}")
        print(f"This tells the server that initialization is complete.\n")
        
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        try:
            response = await client.post(
                server_url,
                json=initialized_notification,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*"
                }
            )
            
            print(f"Status Code: {response.status_code}")
            if response.status_code in [200, 204]:
                print(f"{GREEN}✓ Notification sent successfully{RESET}\n")
            else:
                print(f"{YELLOW}⚠ Unexpected status code: {response.status_code}{RESET}")
                print(f"Response: {response.text}\n")
                
        except Exception as e:
            print(f"{RED}✗ Error: {e}{RESET}\n")
        
        # Test 3: List tools (what Claude.ai needs to show available tools)
        print(f"{YELLOW}[Test 3/4] Requesting 'tools/list'...{RESET}")
        print(f"This is how Claude.ai discovers what tools are available.\n")
        
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        try:
            response = await client.post(
                server_url,
                json=tools_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*"
                }
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print(f"{GREEN}✓ Tools list request successful!{RESET}")
                
                content = response.text
                
                # Check if it's SSE format
                if content.startswith("event:"):
                    # Extract JSON from SSE
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            json_str = line[6:]
                            try:
                                data = json.loads(json_str)
                                if 'result' in data and 'tools' in data['result']:
                                    tools = data['result']['tools']
                                    print(f"\n{GREEN}Found {len(tools)} tool(s):{RESET}")
                                    for tool in tools:
                                        print(f"  • {tool['name']}: {tool.get('description', 'No description')[:80]}")
                            except json.JSONDecodeError:
                                pass
                else:
                    try:
                        data = json.loads(content)
                        if 'result' in data and 'tools' in data['result']:
                            tools = data['result']['tools']
                            print(f"\n{GREEN}Found {len(tools)} tool(s):{RESET}")
                            for tool in tools:
                                print(f"  • {tool['name']}: {tool.get('description', 'No description')[:80]}")
                    except json.JSONDecodeError as e:
                        print(f"{RED}✗ Failed to parse response: {e}{RESET}")
            else:
                print(f"{RED}✗ Tools list request failed!{RESET}")
                print(f"Response: {response.text}\n")
                
        except Exception as e:
            print(f"{RED}✗ Error: {e}{RESET}\n")
        
        # Test 4: Call a tool (if we found any)
        print(f"\n{YELLOW}[Test 4/4] Testing tool invocation...{RESET}")
        print(f"This simulates Claude.ai actually using a tool.\n")
        
        tool_call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_youtube_transcript",
                "arguments": {
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                }
            }
        }
        
        try:
            response = await client.post(
                server_url,
                json=tool_call_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*"
                },
                timeout=60.0  # Tools might take longer
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print(f"{GREEN}✓ Tool call successful!{RESET}")
                content = response.text
                
                # Check if it's SSE format
                if content.startswith("event:"):
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            json_str = line[6:]
                            try:
                                data = json.loads(json_str)
                                if 'result' in data:
                                    result_content = data['result'].get('content', [])
                                    if result_content:
                                        text = result_content[0].get('text', '')
                                        print(f"\nTool result preview:\n{text[:200]}...\n")
                            except json.JSONDecodeError:
                                pass
            else:
                print(f"{RED}✗ Tool call failed!{RESET}")
                print(f"Response: {response.text}\n")
                
        except httpx.TimeoutException:
            print(f"{RED}✗ Tool call timed out{RESET}\n")
        except Exception as e:
            print(f"{RED}✗ Error: {e}{RESET}\n")
    
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}Test Complete!{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")
    
    print(f"{YELLOW}Summary:{RESET}")
    print(f"If all tests passed with ✓, your server should work with Claude.ai.")
    print(f"If you see ✗ or ⚠, those indicate the issues preventing Claude.ai from connecting.\n")


if __name__ == "__main__":
    SERVER_URL = "https://agentictools.uk/mcp"
    
    print(f"\nStarting Claude.ai MCP connector emulation at {datetime.now()}\n")
    asyncio.run(test_mcp_connection(SERVER_URL))