# mcp-test.ps1
# Comprehensive MCP Server Test Script

Write-Host "=== MCP Server Test Suite ===" -ForegroundColor Cyan
Write-Host "Testing: https://agentictools.uk" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "[1/4] Testing Health Endpoint..." -ForegroundColor Yellow
try {
    $healthResponse = Invoke-WebRequest -Uri "https://agentictools.uk/health" -Method GET
    Write-Host "SUCCESS - Health Check" -ForegroundColor Green
    Write-Host "Status: $($healthResponse.StatusCode)" -ForegroundColor Gray
    Write-Host "Response: $($healthResponse.Content)" -ForegroundColor Gray
}
catch {
    Write-Host "FAILED - Health Check" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 2: Find MCP endpoint
Write-Host "[2/4] Finding MCP Endpoint..." -ForegroundColor Yellow
$mcpEndpoints = @(
    "https://agentictools.uk/mcp",
    "https://agentictools.uk/api/mcp",
    "https://agentictools.uk/sse",
    "https://agentictools.uk/messages"
)

$mcpUrl = $null
foreach ($endpoint in $mcpEndpoints) {
    Write-Host "Trying: $endpoint" -ForegroundColor Gray
    try {
        $testBody = @{
            jsonrpc = "2.0"
            id = 1
            method = "initialize"
            params = @{
                protocolVersion = "2024-11-05"
                capabilities = @{}
                clientInfo = @{
                    name = "test-client"
                    version = "1.0.0"
                }
            }
        } | ConvertTo-Json -Depth 10

        # IMPORTANT: Add required Accept header for stateless HTTP mode
        $headers = @{
            "Accept" = "application/json, text/event-stream"
            "Content-Type" = "application/json"
        }

        $testResponse = Invoke-WebRequest -Uri $endpoint -Method POST -Headers $headers -Body $testBody -ErrorAction Stop
        Write-Host "SUCCESS - Found MCP at: $endpoint" -ForegroundColor Green
        Write-Host "Response: $($testResponse.Content)" -ForegroundColor Gray
        $mcpUrl = $endpoint
        break
    }
    catch {
        Write-Host "  Not here ($($_.Exception.Response.StatusCode))" -ForegroundColor DarkGray
    }
}

if (-not $mcpUrl) {
    Write-Host "FAILED - Could not find MCP endpoint" -ForegroundColor Red
    Write-Host "Your health endpoint shows tools are loaded. What is your MCP endpoint path?" -ForegroundColor Yellow
    exit
}
Write-Host ""

# Test 3: List Tools
Write-Host "[3/4] Listing Available Tools..." -ForegroundColor Yellow
try {
    $listBody = @{
        jsonrpc = "2.0"
        id = 2
        method = "tools/list"
        params = @{}
    } | ConvertTo-Json -Depth 10

    $headers = @{
        "Accept" = "application/json, text/event-stream"
        "Content-Type" = "application/json"
    }

    $listResponse = Invoke-WebRequest -Uri $mcpUrl -Method POST -Headers $headers -Body $listBody
    Write-Host "SUCCESS - Tools List" -ForegroundColor Green
    Write-Host "Response: $($listResponse.Content)" -ForegroundColor Gray
}
catch {
    Write-Host "FAILED - Tools List" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 4: Call Tool
Write-Host "[4/4] Testing Tool Invocation (get_youtube_transcript)..." -ForegroundColor Yellow
try {
    $callBody = @{
        jsonrpc = "2.0"
        id = 3
        method = "tools/call"
        params = @{
            name = "get_youtube_transcript"
            arguments = @{
                url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        }
    } | ConvertTo-Json -Depth 10

    $headers = @{
        "Accept" = "application/json, text/event-stream"
        "Content-Type" = "application/json"
    }

    $callResponse = Invoke-WebRequest -Uri $mcpUrl -Method POST -Headers $headers -Body $callBody
    Write-Host "SUCCESS - Tool Invocation" -ForegroundColor Green

    # Parse response - it comes as SSE format
    $content = $callResponse.Content
    if ($content -match 'data: (.+)') {
        $jsonData = $matches[1] | ConvertFrom-Json
        if ($jsonData.result.content) {
            $transcript = $jsonData.result.content[0].text
            Write-Host "Transcript preview: $($transcript.Substring(0, [Math]::Min(200, $transcript.Length)))..." -ForegroundColor Gray
        }
    } else {
        Write-Host "Response: $content" -ForegroundColor Gray
    }
}
catch {
    Write-Host "FAILED - Tool Invocation" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Test Suite Complete ===" -ForegroundColor Cyan
Write-Host "MCP Server URL: $mcpUrl" -ForegroundColor Green
