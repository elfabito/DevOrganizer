@echo off
echo ========================================
echo Building DevOrganizer Executable
echo ========================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Creating executable...
echo.

REM Build the executable
pyinstaller ^
    --onefile ^
    --add-data "templates;templates" ^
    --add-data ".env;." ^
    --hidden-import=groq ^
    --hidden-import=flask ^
    --hidden-import=sqlite3 ^
    --hidden-import=dotenv ^
    --hidden-import=weekly_summary_storage ^
    --hidden-import=ai_service ^
    --hidden-import=storage_sqlite ^
    --icon=NONE ^
    --name="DevOrganizer" ^
    --clean ^
    app.py

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Your executable is in: dist\DevOrganizer.exe
echo.
echo To run: dist\DevOrganizer.exe
echo.
pause
