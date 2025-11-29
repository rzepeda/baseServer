# --- CONFIGURATION ---
$repoUrl = "https://github.com/rzepeda/baseServer.git"
$imageName = "mcp-tool-server"
$containerName = "mcpToolServer"
# Changed host port to 8090 to avoid conflict with your other app
$port = "8090:8080" 

# !!! UPDATE THIS PATH !!!
# Point this to where your .env file is currently located on your Windows machine
$envPath = "C:\Users\rizep\projects\mcpServer\.env"

$tempDir = "$env:TEMP\docker-build-$(Get-Date -Format 'yyyyMMddHHmmss')"

# 1. Clone the repository
Write-Host "Cloning repository..." -ForegroundColor Green
git clone $repoUrl $tempDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to clone repository" -ForegroundColor Red
    exit 1
}

Set-Location $tempDir

# 2. Generate Dockerfile
Write-Host "Generating Dockerfile..." -ForegroundColor Cyan

# Check for requirements.txt
$reqFile = "requirements.txt"
$installCmd = "RUN pip install --no-cache-dir -r requirements.txt"

# If requirements.txt is missing, create an empty one to prevent build errors
if (-not (Test-Path $reqFile)) {
    Write-Host "No requirements.txt found. Creating an empty one..." -ForegroundColor Yellow
    New-Item -Path . -Name "requirements.txt" -ItemType "file" -Value ""
}

$dockerfileContent = @"
# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy all files
COPY . /app

# Install dependencies
$installCmd

# Expose the internal port
EXPOSE 8080

# Run the app as a module
CMD ["python", "-m", "src"]
"@

Set-Content -Path "Dockerfile" -Value $dockerfileContent

# 3. Build the Docker image
Write-Host "Building Docker image '$imageName'..." -ForegroundColor Green
docker build -t $imageName .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build Docker image" -ForegroundColor Red
    Set-Location $PSScriptRoot
    Remove-Item -Recurse -Force $tempDir
    exit 1
}

# 4. Cleanup existing container
Write-Host "Checking for existing container..." -ForegroundColor Green
$existingContainer = docker ps -a --filter "name=$containerName" --format "{{.Names}}"
if ($existingContainer -eq $containerName) {
    Write-Host "Stopping and removing existing container..." -ForegroundColor Yellow
    docker stop $containerName
    docker rm $containerName
}

# 5. Run new container with .env injection
Write-Host "Running new container..." -ForegroundColor Green

if (Test-Path $envPath) {
    Write-Host "Found .env file at $envPath. Injecting secrets..." -ForegroundColor Cyan
    docker run -d -p $port --env-file $envPath --name $containerName --restart unless-stopped $imageName
}
else {
    Write-Host "WARNING: .env file NOT found at: $envPath" -ForegroundColor Red
    Write-Host "Starting container without secrets (it may crash)..." -ForegroundColor Yellow
    docker run -d -p $port --name $containerName --restart unless-stopped $imageName
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to run container" -ForegroundColor Red
    Set-Location $PSScriptRoot
    Remove-Item -Recurse -Force $tempDir
    exit 1
}

# 6. Cleanup temp files
Write-Host "Cleaning up temporary files..." -ForegroundColor Green
Set-Location $PSScriptRoot
Remove-Item -Recurse -Force $tempDir

Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "Container '$containerName' is running on http://localhost:8090"