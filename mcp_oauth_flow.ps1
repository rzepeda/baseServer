<#
.SYNOPSIS
    A PowerShell script to perform the OAuth 2.0 Authorization Code Flow with PKCE.
.DESCRIPTION
    This script emulates the full OAuth 2.0 flow, including PKCE key generation,
    user authorization, token exchange, and token verification. It is the PowerShell
    equivalent of the 'mcp_oauth_flow.sh' script.
#>

# --- CONFIGURATION (Edit these values) ---
$McpUrl = "http://localhost:8080"
$ClientId = "mcpServer" # Or your specific Client ID
$ClientSecret = "YOUR_CLIENT_SECRET" # Leave as is if the client is public, otherwise replace
$RedirectUri = "http://localhost:6274/oauth/callback"

# --- HELPER FUNCTIONS ---

# PowerShell's Invoke-RestMethod handles JSON conversion automatically.
# This function handles Base64 URL-safe encoding (RFC 4648).
function ConvertTo-Base64UrlSafeString {
    param([byte[]]$Bytes)
    return [System.Convert]::ToBase64String($Bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}


# =============================================================================
# --- MAIN SCRIPT ---
# =============================================================================

Write-Host "`n--- MCP OAuth 2.0 E2E Flow Test (PowerShell) ---" -ForegroundColor Cyan

# --- [Step 0] Generating PKCE Keys ---
Write-Host "`n[Step 0] Generating PKCE Keys..." -ForegroundColor Green

# 1. Generate Code Verifier (High-entropy random string)
$verifierBytes = [byte[]]::new(32)
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($verifierBytes)
$CodeVerifier = ConvertTo-Base64UrlSafeString -Bytes $verifierBytes

Write-Host "Code Verifier: $CodeVerifier" -ForegroundColor Gray

# 2. Generate Code Challenge
$verifierBytesForHash = [System.Text.Encoding]::UTF8.GetBytes($CodeVerifier)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$challengeBytes = $sha256.ComputeHash($verifierBytesForHash)
$CodeChallenge = ConvertTo-Base64UrlSafeString -Bytes $challengeBytes

Write-Host "Code Challenge: $CodeChallenge" -ForegroundColor Gray


# --- [Step 1] Discovery: Fetching OAuth Endpoints ---
Write-Host "`n[Step 1] Discovery: Fetching OAuth Endpoints..." -ForegroundColor Green
try {
    $discoveryUrl = "$McpUrl/.well-known/oauth-authorization-server"
    $discoveryDoc = Invoke-RestMethod -Uri $discoveryUrl -Method Get
    
    # Resolve relative URLs if necessary (for completeness)
    $authEndpoint = [System.URI]::new([System.URI]$McpUrl, $discoveryDoc.authorization_endpoint).AbsoluteUri
    $tokenEndpoint = [System.URI]::new([System.URI]$McpUrl, $discoveryDoc.token_endpoint).AbsoluteUri

    Write-Host "Auth Endpoint:  $authEndpoint"
    Write-Host "Token Endpoint: $tokenEndpoint"
}
catch {
    Write-Host "`n[ERROR] Failed to fetch or parse discovery document from $McpUrl" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}


# --- [Step 2 & 3] User Login Interaction ---
Write-Host "`n[Step 2 & 3] User Login Interaction" -ForegroundColor Green

$scope = "openid phone address basic service_account offline_access acr web-origins email microprofile-jwt roles profile organization"
$state = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ })

$queryParams = @{
    response_type = "code"
    client_id = $ClientId
    redirect_uri = $RedirectUri
    scope = $scope
    state = $state
    code_challenge = $CodeChallenge
    code_challenge_method = "S256"
    prompt = "consent"
}
$encodedQuery = ($queryParams.Keys | ForEach-Object { "$($_)=$( [System.Web.HttpUtility]::UrlEncode($queryParams.$_) )" }) -join '&'
$loginUrl = "$authEndpoint?$encodedQuery"

Write-Host "`n1. Copy the URL below and open it in your browser." -ForegroundColor Yellow
Write-Host "2. Log in." -ForegroundColor Yellow
Write-Host "3. You will be redirected to a page that may show an error (this is okay)." -ForegroundColor Yellow
Write-Host "4. Copy the ENTIRE URL from your browser's address bar after the redirect." -ForegroundColor Yellow

Write-Host "`nURL TO VISIT:" -ForegroundColor DarkGreen
Write-Host $loginUrl

$redirectedUrl = Read-Host "`nPaste the full redirected URL here"

try {
    $uri = [System.URI]$redirectedUrl
    $queryParts = [System.Web.HttpUtility]::ParseQueryString($uri.Query)
    $authCode = $queryParts["code"]
    $returnedState = $queryParts["state"]

    if (-not $authCode) { throw "Could not extract 'code' from the provided URL." }
    if ($state -ne $returnedState) { throw "CSRF detected! The 'state' value did not match." }

    Write-Host "`nSuccessfully extracted Authorization Code: $authCode" -ForegroundColor DarkGreen
}
catch {
    Write-Host "`n[ERROR] Failed to parse the redirected URL." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}


# --- [Step 4] Token Exchange: Swapping Code for Access Token ---
Write-Host "`n[Step 4] Token Exchange: Swapping Code for Access Token..." -ForegroundColor Green

$tokenBody = @{
    grant_type = "authorization_code"
    code = $authCode
    redirect_uri = $RedirectUri
    code_verifier = $CodeVerifier
    client_id = $ClientId
}

$tokenHeaders = @{}
if (-not [string]::IsNullOrEmpty($ClientSecret) -and $ClientSecret -ne "YOUR_CLIENT_SECRET") {
    $basicAuth = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes("${ClientId}:${ClientSecret}"))
    $tokenHeaders["Authorization"] = "Basic $basicAuth"
}

try {
    $tokenResponse = Invoke-RestMethod -Uri $tokenEndpoint -Method Post -Body $tokenBody -Headers $tokenHeaders
    $accessToken = $tokenResponse.access_token

    if (-not $accessToken) { throw "No access_token found in response." }

    Write-Host "`n[SUCCESS] Token Exchange Complete!" -ForegroundColor DarkGreen
}
catch {
    Write-Host "`n[FAILURE] No access_token found." -ForegroundColor Red
    Write-Host "Server Response: $($_.Exception.Response.Content)" -ForegroundColor Red
    exit 1
}


# --- [Step 5] Verification (Testing Non-Existent Endpoint) ---
Write-Host "`n[Step 5] Verification: Testing token against the non-existent '/v1/tools' endpoint..." -ForegroundColor Green
$testEndpointV1 = "$McpUrl/v1/tools"
Write-Host "Target: $testEndpointV1"

$authHeader = @{ Authorization = "Bearer $accessToken" }

try {
    # Using Invoke-WebRequest because Invoke-RestMethod throws a terminating error on 404
    Invoke-WebRequest -Uri $testEndpointV1 -Method Get -Headers $authHeader -ErrorAction Stop
}
catch {
    $statusCode = $_.Exception.Response.StatusCode
    $responseBody = $_.Exception.Response.Content
    Write-Host "`nServer Response for /v1/tools (Status $statusCode):" -ForegroundColor Yellow
    Write-Host $responseBody
}


# --- [Step 6] Verification (Testing Correct Endpoint) ---
Write-Host "`n[Step 6] Verification: Reusing token to test the correct '/tools/list' endpoint..." -ForegroundColor Green
$testEndpointTools = "$McpUrl/tools/list"
Write-Host "Target: $testEndpointTools"

try {
    $toolsResponse = Invoke-RestMethod -Uri $testEndpointTools -Method Get -Headers $authHeader
    $statusCode = $toolsResponse.psobject.Properties.Match('StatusCode')[0].Value
    
    Write-Host "`nServer Response for /tools/list (Status $statusCode):"
    Write-Host "`n[FINAL SUCCESS] Successfully authenticated and received a valid response!" -ForegroundColor DarkGreen
    
    # Pretty-print the JSON response
    Write-Host ($toolsResponse | ConvertTo-Json -Depth 5)
}
catch {
    Write-Host "`n[FINAL FAILURE] Request to $testEndpointTools failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
