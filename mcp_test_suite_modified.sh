#!/usr/bin/env bash

# === MCP Server Test Suite ===

set -e

CYAN="\033[36m"
YELLOW="\033[33m"
GREEN="\033[32m"
RED="\033[31m"
GRAY="\033[90m"
RESET="\033[0m"

BASE_URL="http://localhost:8080"

echo -e "${CYAN}=== MCP Server Test Suite ===${RESET}"
echo -e "${CYAN}Testing: ${BASE_URL}${RESET}"
echo ""

########################################
# Test 1 – Health Check
########################################
echo -e "${YELLOW}[1/5] Testing Health Endpoint...${RESET}"

if health_json=$(curl -s -w "\n%{http_code}" $BASE_URL/health); then
    body=$(echo "$health_json" | head -n -1)
    code=$(echo "$health_json" | tail -n 1)
    if [[ $code == 200 ]]; then
        echo -e "${GREEN}SUCCESS - Health Check${RESET}"
        echo -e "${GRAY}Status: $code${RESET}"
        echo -e "${GRAY}Response: $body${RESET}"
    else
        echo -e "${RED}FAILED - Health Check${RESET}"
        echo -e "${RED}Status: $code${RESET}"
        echo -e "${RED}Body: $body${RESET}"
        exit 1
    fi
else
    echo -e "${RED}FAILED - Health Check${RESET}"
    exit 1
fi
echo ""

########################################
# Test 2 – List Tools
########################################
echo -e "${YELLOW}[2/5] Listing Available Tools...${RESET}"

if list_json=$(curl -s -w "\n%{http_code}" $BASE_URL/tools/list); then
    body=$(echo "$list_json" | head -n -1)
    code=$(echo "$list_json" | tail -n 1)
    if [[ $code == 200 ]]; then
        echo -e "${GREEN}SUCCESS - Tools List${RESET}"
        echo -e "${GRAY}Status: $code${RESET}"
        echo -e "${GRAY}Response: $body${RESET}"
    else
        echo -e "${RED}FAILED - Tools List${RESET}"
        echo -e "${RED}Status: $code${RESET}"
        echo -e "${RED}Body: $body${RESET}"
        exit 1
    fi
else
    echo -e "${RED}FAILED - Tools List${RESET}"
    exit 1
fi
echo ""

########################################
# Test 3 – CORS Preflight Test
########################################
echo -e "${YELLOW}[3/5] Testing CORS Preflight (OPTIONS)...${RESET}"

if headers=$(curl -s -I -X OPTIONS -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: POST" $BASE_URL/tools/invoke); then
    if echo "$headers" | grep -q "HTTP/1.1 200 OK"; then
        echo -e "${GREEN}SUCCESS - CORS Preflight${RESET}"
        echo -e "${GRAY}$headers${RESET}"
    else
        echo -e "${RED}FAILED - CORS Preflight${RESET}"
        echo -e "${RED}$headers${RESET}"
        exit 1
    fi
else
    echo -e "${RED}FAILED - CORS Preflight curl command failed${RESET}"
    exit 1
fi
echo ""

########################################
# Test 4 – CORS Actual Request Test
########################################
echo -e "${YELLOW}[4/5] Testing CORS Actual Request (POST)...${RESET}"

invoke_payload=$(jq -n \
    --arg tool_name "youtube_transcript_tool" \
    '{
        tool_name: $tool_name,
        parameters: {
            video_id: "dQw4w9WgXcQ"
        }
    }'
)

if headers=$(curl -s -I -X POST -H "Origin: http://localhost:5173" -H "Content-Type: application/json" --data "$invoke_payload" $BASE_URL/tools/invoke); then
    if echo "$headers" | grep -q "access-control-allow-origin: http://localhost:5173"; then
        echo -e "${GREEN}SUCCESS - CORS Headers Present${RESET}"
        echo -e "${GRAY}$headers${RESET}"
    else
        echo -e "${RED}FAILED - CORS Headers Missing${RESET}"
        echo -e "${RED}$headers${RESET}"
        exit 1
    fi
else
    echo -e "${RED}FAILED - CORS Actual Request curl command failed${RESET}"
    exit 1
fi
echo ""


########################################
# Test 5 – Call Tool
########################################
echo -e "${YELLOW}[5/5] Testing Tool Invocation (youtube_transcript_tool)...${RESET}"

invoke_payload=$(jq -n \
    --arg tool_name "youtube_transcript_tool" \
    '{
        tool_name: $tool_name,
        parameters: {
            video_id: "dQw4w9WgXcQ"
        }
    }'
)

if response_json=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" --data "$invoke_payload" $BASE_URL/tools/invoke); then
    body=$(echo "$response_json" | head -n -1)
    code=$(echo "$response_json" | tail -n 1)
    if [[ $code == 200 ]]; then
        echo -e "${GREEN}SUCCESS - Tool Invocation${RESET}"
        echo -e "${GRAY}Status: $code${RESET}"
        echo -e "${GRAY}Response: $body${RESET}"
    else
        echo -e "${RED}FAILED - Tool Invocation${RESET}"
        echo -e "${RED}Status: $code${RESET}"
        echo -e "${RED}Body: $body${RESET}"
        exit 1
    fi
else
    echo -e "${RED}FAILED - Tool Invocation curl command failed${RESET}"
    exit 1
fi


echo ""
echo -e "${CYAN}=== Test Suite Complete ===${RESET}"
