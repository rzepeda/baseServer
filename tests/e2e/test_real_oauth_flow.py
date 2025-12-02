"""
This module is a semi-automated end-to-end test for the full OAuth 2.0
Authorization Code Flow with PKCE, based on the working 'mcp_oauth_flow.sh' script.

This is NOT a standard automated pytest test. It requires manual user interaction.

Instructions:
1. Ensure the main server is running.
2. Ensure your .env file is populated with the correct values for:
   - MCP_URL (e.g., http://localhost:8080)
   - CLIENT_ID
   - CLIENT_SECRET
3. Run this script from the root of the project:
   `python -m tests.e2e.test_real_oauth_flow`
4. Follow the prompts in your terminal.
"""

import hashlib
import os
import secrets
import base64
import httpx
import json
from dotenv import load_dotenv

def url_encode(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s)

def get_json_value(json_str: str, key: str) -> str:
    try:
        return json.loads(json_str).get(key, '')
    except json.JSONDecodeError:
        return ''

def main():
    """Orchestrates the end-to-end OAuth flow test."""
    load_dotenv()

    # --- CONFIGURATION ---
    mcp_url = os.getenv("MCP_URL", "http://localhost:8080")
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    
    if not all([client_id, client_secret]):
        print("\n\033[0;31mError: OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set in your .env file.\033[0m")
        return

    redirect_uri = "http://localhost:6274/oauth/callback" # As seen in the provided URL

    print("\n\033[1;34m--- MCP OAuth 2.0 E2E Flow Test ---")

    # --- Step 0: Generate PKCE Keys ---
    print("\n\033[0;36m[Step 0] Generating PKCE Keys...\033[0m")
    code_verifier = secrets.token_urlsafe(64)
    print(f"\033[0;90mCode Verifier: {code_verifier}\033[0m")
    
    challenge_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_hash).decode('utf-8').replace('=', '')
    print(f"\033[0;90mCode Challenge: {code_challenge}\033[0m")

    # --- Step 1: Discovery ---
    print("\n\033[0;36m[Step 1] Discovery: Fetching OAuth Endpoints...\033[0m")
    try:
        discovery_response = httpx.get(f"{mcp_url}/.well-known/oauth-authorization-server", timeout=10)
        discovery_response.raise_for_status()
        discovery_json = discovery_response.json()
    except (httpx.RequestError, json.JSONDecodeError) as e:
        print(f"\n\033[0;31mError: Failed to fetch or parse discovery document from {mcp_url}.\033[0m")
        print(f"Details: {e}")
        return

    auth_endpoint = discovery_json.get("authorization_endpoint")
    token_endpoint = discovery_json.get("token_endpoint")

    if not all([auth_endpoint, token_endpoint]):
        print("\n\033[0;31mError: Could not find 'authorization_endpoint' or 'token_endpoint' in discovery document.\033[0m")
        return
        
    print(f"\033[0;37mAuth Endpoint:  {auth_endpoint}\033[0m")
    print(f"\033[0;37mToken Endpoint: {token_endpoint}\033[0m")
    
    # --- Step 2 & 3: User Login Interaction ---
    print("\n\033[0;36m[Step 2 & 3] User Login Interaction\033[0m")
    scope = "openid phone address basic service_account offline_access acr web-origins email microprofile-jwt roles profile organization"
    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }
    
    login_url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
    
    print("\n\033[0;33m1. Copy the URL below and open it in your browser.")
    print("2. Log in.")
    print("3. You will be redirected to a page that may show an error (this is okay).")
    print("4. Copy the ENTIRE URL from your browser's address bar after the redirect.\033[0m")
    print("\n\033[0;32mURL TO VISIT:\033[0m")
    print(login_url)
    
    redirected_url = input("\nPaste the full redirected URL here: ")
    
    try:
        parsed_url = urllib.parse.urlparse(redirected_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        auth_code = query_params.get("code", [None])[0]
        returned_state = query_params.get("state", [None])[0]
    except Exception:
        auth_code = None
        returned_state = None

    if not auth_code:
        print("\n\033[0;31mError: Could not extract 'code' from the provided URL.\033[0m")
        return
    
    if state != returned_state:
        print("\n\033[0;31mError: CSRF detected! The 'state' value did not match.\033[0m")
        return

    print(f"\n\033[0;32mSuccessfully extracted Authorization Code: {auth_code}\033[0m")

    # --- Step 4: Token Exchange ---
    print("\n\033[0;36m[Step 4] Token Exchange: Swapping Code for Access Token...\033[0m")
    token_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    
    try:
        token_response = httpx.post(token_endpoint, data=token_data)
        token_response.raise_for_status()
        token_json = token_response.json()
    except (httpx.RequestError, json.JSONDecodeError) as e:
        print(f"\n\033[0;31mError: Failed during token exchange.\033[0m")
        print(f"Details: {e}")
        if hasattr(e, 'response'):
            print(f"Server Response: {e.response.text}")
        return

    access_token = token_json.get("access_token")

    if not access_token:
        print("\n\033[0;31m[FAILURE] No access_token found in response.\033[0m")
        print(f"Full Response: {token_json}")
        return

    print("\n\033[0;32m[SUCCESS] Token Exchange Complete!\033[0m")

    # --- Step 5: Verification (SSE Flow) ---
    print("\n\033[0;36m[Step 5] Verification: Testing Token against SSE Server...\033[0m")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. Connect to /sse to get a session_id
    sse_endpoint = f"{mcp_url}/sse"
    print(f"Target (SSE Connect): {sse_endpoint}")
    
    try:
        with httpx.stream("GET", sse_endpoint, headers=headers, timeout=10) as sse_response:
            sse_response.raise_for_status()
            
            # The first event should contain the session_id
            session_id = None
            for line in sse_response.iter_lines():
                if line.startswith("data:"):
                    data = json.loads(line.split("data:", 1)[1])
                    if data.get("event") == "session_created":
                        session_id = data.get("session_id")
                        print(f"\033[0;32mSuccessfully connected to SSE and got session_id: {session_id}\033[0m")
                        break # Got what we needed
            
            if not session_id:
                print("\n\033[0;31m[FINAL FAILURE] Did not receive a session_id from the /sse endpoint.\033[0m")
                return

    except httpx.RequestError as e:
        print(f"\n\033[0;31m[FINAL FAILURE] Request to /sse endpoint failed.\033[0m")
        print(f"Details: {e}")
        if hasattr(e, 'response'):
            print(f"Server Response: {e.response.text}")
        return

    # 2. POST message to /messages/ with the session_id
    messages_endpoint = f"{mcp_url}/messages/?session_id={session_id}"
    print(f"Target (POST Message): {messages_endpoint}")

    rpc_payload = {
        "jsonrpc": "2.0",
        "id": "e2e-test-1",
        "method": "tools/list",
        "params": {},
    }

    # The /messages/ endpoint does not require the Authorization header again
    # as the session is already authenticated.
    message_headers = {"Content-Type": "application/json"}
    
    try:
        final_response = httpx.post(messages_endpoint, headers=message_headers, json=rpc_payload, timeout=10)
        final_response.raise_for_status()
        
        print("\n\033[0;32m[FINAL SUCCESS] Authenticated request to server succeeded!\033[0m")
        print(f"\n\033[0;37mServer Response (Status {final_response.status_code}):\033[0m")
        try:
            print(json.dumps(final_response.json(), indent=2))
        except json.JSONDecodeError:
            print(final_response.text)

    except httpx.RequestError as e:
        print(f"\n\033[0;31m[FINAL FAILURE] Authenticated request to /messages/ failed.\033[0m")
        print(f"Details: {e}")
        if hasattr(e, 'response'):
            print(f"Server Response: {e.response.text}")
        return

if __name__ == "__main__":
    import urllib.parse # Add missing import for main execution
    main()
