#!/bin/bash
# ==========================================
# MCP OAuth 2.0 Flow Emulator (Bash/Linux)
# WITH PKCE SUPPORT
# ==========================================

# --- CONFIGURATION (Edit these) ---
MCP_URL="http://localhost:8080"
CLIENT_ID="mtClaude8394"
CLIENT_SECRET="wH7O4LkoLg57Qk4ziSdFdLYJjoLAcpqm" # Leave empty if public
REDIRECT_URI="http://localhost:6274/oauth/callback"
TEST_ENDPOINT="$MCP_URL/v1/tools" # Endpoint to verify token against

# --- DEPENDENCY CHECK ---
for cmd in curl openssl python3; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: '$cmd' is not installed. Please install it to run this script."
        exit 1
    fi
done

# --- HELPER FUNCTIONS ---

# Robust URL encoding using Python
url_encode() {
    python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$1"
}

# Robust JSON extraction using Python
get_json_value() {
    # Usage: echo $json | get_json_value "key_name"
    python3 -c "import sys, json; print(json.load(sys.stdin).get('$1', ''))"
}

# Generate Random String (URL Safe)
generate_random_string() {
    local length=$1
    openssl rand -base64 $((length * 2)) | tr -dc 'a-zA-Z0-9-._~' | head -c $length
}

# Base64 URL Encode (RFC 4648)
base64_url_encode() {
    openssl base64 -e -A | tr '+' '-' | tr '/' '_' | tr -d '='
}

echo -e "\n\033[0;36m[Step 0] Generating PKCE Keys...\033[0m"

# 1. Generate Code Verifier (High entropy random string)
CODE_VERIFIER=$(generate_random_string 64)
echo -e "\033[0;90mCode Verifier: $CODE_VERIFIER\033[0m"

# 2. Generate Code Challenge
CODE_CHALLENGE=$(echo -n "$CODE_VERIFIER" | openssl dgst -sha256 -binary | base64_url_encode)
echo -e "\033[0;90mCode Challenge: $CODE_CHALLENGE\033[0m"


echo -e "\n\033[0;36m[Step 1] Discovery: Fetching OAuth Endpoints...\033[0m"

DISCOVERY_JSON=$(curl -s "$MCP_URL/.well-known/oauth-authorization-server")

if [ -z "$DISCOVERY_JSON" ]; then
    echo "Error: Failed to fetch discovery document from $MCP_URL"
    exit 1
fi

AUTH_ENDPOINT_RAW=$(echo "$DISCOVERY_JSON" | get_json_value "authorization_endpoint")
TOKEN_ENDPOINT_RAW=$(echo "$DISCOVERY_JSON" | get_json_value "token_endpoint")

# Handle relative URLs
resolve_url() {
    local base=$1
    local path=$2
    if [[ "$path" =~ ^http ]]; then
        echo "$path"
    else
        echo "${base%/}/${path#/}"
    fi
}

AUTH_ENDPOINT=$(resolve_url "$MCP_URL" "$AUTH_ENDPOINT_RAW")
TOKEN_ENDPOINT=$(resolve_url "$MCP_URL" "$TOKEN_ENDPOINT_RAW")

echo -e "\033[0;37mAuth Endpoint:  $AUTH_ENDPOINT\033[0m"
echo -e "\033[0;37mToken Endpoint: $TOKEN_ENDPOINT\033[0m"


# --- CONSTRUCT URL ---
echo -e "\n\033[0;36m[Step 2 & 3] User Login Interaction\033[0m"

SCOPE_RAW="openid phone address basic service_account offline_access acr web-origins email microprofile-jwt roles profile organization"
STATE_RAW=$(generate_random_string 16)

P_CLIENT_ID=$(url_encode "$CLIENT_ID")
P_REDIRECT=$(url_encode "$REDIRECT_URI")
P_SCOPE=$(url_encode "$SCOPE_RAW")
P_STATE=$(url_encode "$STATE_RAW")
P_CHAL=$(url_encode "$CODE_CHALLENGE")

LOGIN_URL="$AUTH_ENDPOINT?response_type=code&client_id=$P_CLIENT_ID&redirect_uri=$P_REDIRECT&scope=$P_SCOPE&state=$P_STATE&code_challenge=$P_CHAL&code_challenge_method=S256&prompt=consent"

# --- PORT CONFLICT CHECK ---
REDIRECT_PORT=$(echo "$REDIRECT_URI" | grep -oP ':\K\d+')
if [ -n "$REDIRECT_PORT" ]; then
    # Simple check if port is listening (bash specific /dev/tcp)
    if (echo > /dev/tcp/localhost/$REDIRECT_PORT) &>/dev/null; then
         echo -e "\n\033[0;41;37m WARNING: Port $REDIRECT_PORT is currently in use! \033[0m"
         echo -e "\033[0;33mThe application running on port $REDIRECT_PORT (e.g., Inspector) might intercept the callback and hide the code."
         echo -e "RECOMMENDATION: Stop the Inspector tool momentarily before clicking the link below."
         echo -e "If the port is closed, the browser will show 'Connection Refused', but the CODE will stay visible in the address bar.\033[0m"
    fi
fi

echo -e "\n\033[0;33m1. Copy the URL below and open it in your browser."
echo "2. Log in."
echo "3. If the page shows an error or 'Connection Refused', LOOK AT THE ADDRESS BAR."
echo "4. Copy the value of 'code=...' (everything after code= and before &state=).\033[0m"
echo -e "\n\033[0;32mURL TO VISIT:\033[0m"
echo "$LOGIN_URL"

echo ""
read -p "Paste the 'code' value here: " AUTH_CODE

# Strip whitespace
AUTH_CODE=$(echo "$AUTH_CODE" | xargs)

if [ -z "$AUTH_CODE" ]; then
    echo "Error: No code provided."
    exit 1
fi

echo -e "\n\033[0;36m[Step 4] Token Exchange: Swapping Code for Access Token...\033[0m"

CURL_ARGS=(
    "-s" "-X" "POST" "$TOKEN_ENDPOINT"
    "-d" "grant_type=authorization_code"
    "-d" "code=$AUTH_CODE"
    "-d" "redirect_uri=$REDIRECT_URI"
    "-d" "code_verifier=$CODE_VERIFIER"
    "-d" "client_id=$CLIENT_ID"
)

if [ -n "$CLIENT_SECRET" ] && [ "$CLIENT_SECRET" != "YOUR_CLIENT_SECRET" ]; then
    CURL_ARGS+=("-u" "$CLIENT_ID:$CLIENT_SECRET")
fi

TOKEN_RESPONSE=$(curl "${CURL_ARGS[@]}")

echo -e "\033[0;37mRaw Response:\033[0m"
echo "$TOKEN_RESPONSE"

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | get_json_value "access_token")

if [ -n "$ACCESS_TOKEN" ]; then
    echo -e "\n\033[0;32m[SUCCESS] Emulation Complete!\033[0m"
    echo "Access Token: $ACCESS_TOKEN"

    echo -e "\n\033[0;36m[Step 5] Verification: Testing Token against Server...\033[0m"
    echo "Target: $TEST_ENDPOINT"
    
    # We use -k just in case it's https with self-signed certs locally, 
    # though usually localhost is http.
    TEST_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "$TEST_ENDPOINT")
    
    echo -e "\033[0;37mServer Response:\033[0m"
    echo "$TEST_RESPONSE"
else
    echo -e "\n\033[0;31m[FAILURE] No access_token found.\033[0m"
fi



# --- Step 6: Verification (Testing Correct Endpoint) ---
echo -e "\n\033[0;36m[Step 6] Verification: Reusing token to test the correct '/tools/list' endpoint...\033[0m"

# Define the correct endpoint
CORRECT_TEST_ENDPOINT="$MCP_URL/tools/list"
echo "Target: $CORRECT_TEST_ENDPOINT"

# Reuse the ACCESS_TOKEN to make the request
CORRECT_TEST_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "$CORRECT_TEST_ENDPOINT")

echo -e "\n\033[0;37mServer Response for /tools/list:\033[0m"
# Attempt to pretty-print JSON using Python's json.tool if available
if command -v python3 &> /dev/null && echo "$CORRECT_TEST_RESPONSE" | python3 -m json.tool &> /dev/null; then
    echo "$CORRECT_TEST_RESPONSE" | python3 -m json.tool
else
    echo "$CORRECT_TEST_RESPONSE"
fi
