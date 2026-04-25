# Start Services Script
# Run this after docker compose build completes

Write-Host "=== Starting Docker Services ===" -ForegroundColor Cyan

# Start all services
Write-Host "`nStarting services..." -ForegroundColor Yellow
docker compose up -d

# Wait a moment for services to initialize
Start-Sleep -Seconds 5

# Check service status
Write-Host "`n=== Service Status ===" -ForegroundColor Cyan
docker compose ps

# Check health endpoints
Write-Host "`n=== Health Checks ===" -ForegroundColor Cyan

Write-Host "`nBackend Health:" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ Backend is healthy (Status: $($response.StatusCode))" -ForegroundColor Green
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 3
} catch {
    Write-Host "❌ Backend not responding yet: $_" -ForegroundColor Red
    Write-Host "   Wait a few more seconds and try again" -ForegroundColor Yellow
}

Write-Host "`nAPI Status:" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:8000/api/status -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ API is responding (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ API not responding yet: $_" -ForegroundColor Red
}

Write-Host "`nFrontend:" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:80 -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ Frontend is accessible (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ Frontend not responding yet: $_" -ForegroundColor Red
}

# Verify R installation
Write-Host "`n=== R Installation Verification ===" -ForegroundColor Cyan
Write-Host "Checking R version..." -ForegroundColor Yellow
docker compose exec -T backend R --version 2>&1 | Select-Object -First 3

Write-Host "`nTesting R packages..." -ForegroundColor Yellow
docker compose exec -T backend R -e "library(DESeq2); library(edgeR); cat('✅ DESeq2 and edgeR loaded successfully\n')" 2>&1

Write-Host "`n=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. Open http://localhost:80 in your browser" -ForegroundColor Green
Write-Host "2. Check API docs at http://localhost:8000/docs" -ForegroundColor Green
Write-Host "3. Run tests: cd backend && python -m pytest tests -v" -ForegroundColor Green
