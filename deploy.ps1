# 🚀 ALL-in-One Deployment Helper for Windows
# This script helps you deploy to Render

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 ALL-in-One Email Platform Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "render.yaml")) {
    Write-Host "❌ Error: render.yaml not found!" -ForegroundColor Red
    Write-Host "Please run this script from the project root directory." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Project structure verified" -ForegroundColor Green
Write-Host ""

Write-Host "📋 Deployment Checklist:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Current Status:" -ForegroundColor White
Write-Host "  ✅ Backend API: Running at https://all-in-one-tdxd.onrender.com" -ForegroundColor Green
Write-Host "  ⏳ Worker Service: Needs to be created" -ForegroundColor Yellow
Write-Host "  ⏳ Frontend: Needs to be created" -ForegroundColor Yellow
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "📝 DEPLOYMENT INSTRUCTIONS" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "OPTION 1: Automatic Deployment (Recommended)" -ForegroundColor Green
Write-Host "--------------------------------------------" -ForegroundColor White
Write-Host "1. Go to: https://dashboard.render.com/blueprints" -ForegroundColor White
Write-Host "2. Find: adamtheplanetarium/ALL-in-One" -ForegroundColor White
Write-Host "3. Click: 'New Blueprint Instance' or 'Sync'" -ForegroundColor White
Write-Host "4. Click: 'Apply'" -ForegroundColor White
Write-Host "5. Wait 5-10 minutes for deployment" -ForegroundColor White
Write-Host ""

Write-Host "OPTION 2: Manual Deployment" -ForegroundColor Yellow
Write-Host "--------------------------------------------" -ForegroundColor White
Write-Host "Follow instructions in DEPLOY_NOW.md" -ForegroundColor White
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "📊 WHAT WILL BE DEPLOYED" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  1. Backend API (Python/Flask)        - $7/month" -ForegroundColor White
Write-Host "  2. Celery Worker (Background Jobs)   - $7/month" -ForegroundColor White
Write-Host "  3. Frontend (React/Vite)            - FREE" -ForegroundColor White
Write-Host "  4. PostgreSQL Database              - $7/month" -ForegroundColor White
Write-Host "  5. Redis Cache                      - $10/month" -ForegroundColor White
Write-Host "  -------------------------------------------" -ForegroundColor White
Write-Host "  Total Monthly Cost:                  $31/month" -ForegroundColor Green
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🔗 USEFUL LINKS" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Render Dashboard:  https://dashboard.render.com" -ForegroundColor White
Write-Host "GitHub Repository: https://github.com/adamtheplanetarium/ALL-in-One" -ForegroundColor White
Write-Host "Backend API:       https://all-in-one-tdxd.onrender.com" -ForegroundColor White
Write-Host "Frontend (soon):   https://allinone-frontend.onrender.com" -ForegroundColor White
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🎯 NEXT STEPS" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Open Render Dashboard" -ForegroundColor Yellow
Write-Host "2. Apply Blueprint deployment" -ForegroundColor Yellow
Write-Host "3. Wait for all services to deploy" -ForegroundColor Yellow
Write-Host "4. Open frontend URL and register" -ForegroundColor Yellow
Write-Host "5. Start creating email campaigns!" -ForegroundColor Yellow
Write-Host ""

Write-Host "Press any key to open Render Dashboard..." -ForegroundColor Green
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Start-Process "https://dashboard.render.com/blueprints"

Write-Host ""
Write-Host "✨ Good luck with your deployment! ✨" -ForegroundColor Cyan
Write-Host ""
