@echo off
echo ========================================
echo Dev Project Organizer
echo ========================================
echo.

REM Check if GROQ_API_KEY is set
if "%GROQ_API_KEY%"=="" (
    echo WARNING: GROQ_API_KEY environment variable is not set!
    echo.
    echo Please get your FREE Groq API key from:
    echo   https://console.groq.com/keys
    echo.
    echo Then either:
    echo   1. Set environment variable: set GROQ_API_KEY=your-api-key-here
    echo   2. Or create a .env file with: GROQ_API_KEY=your-api-key-here
    echo.
    echo Note: The app will try to load from .env file automatically.
    echo.
    pause
)

echo Starting Flask application...
echo.
python app.py

pause
