@echo off
echo ========================================
echo Admin Tools Installation for Biomarker Identifier
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✅ Running with administrator privileges
) else (
    echo ❌ ERROR: This script must be run as administrator
    echo.
    echo Please:
    echo 1. Right-click this file
    echo 2. Select "Run as administrator"
    echo 3. Try again
    echo.
    pause
    exit /b 1
)

echo.
echo 🚀 Starting admin tools installation...
echo.

REM Run the Python installation script
python scripts/confirm_admin_installations.py

echo.
echo 🎉 Installation process completed!
echo.
echo 📋 Next steps:
echo 1. Restart your computer if Docker or WSL was installed
echo 2. Start Docker Desktop if installed
echo 3. Set up PostgreSQL database if installed
echo 4. Install frontend dependencies: cd frontend ^&^& npm install
echo 5. Test the installation: python tests/test_week5_python_only.py
echo.
pause
