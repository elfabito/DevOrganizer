@echo off
echo ========================================
echo Dev Project Organizer - Setup
echo ========================================
echo.

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Get your FREE Groq API key from:
echo    https://console.groq.com/keys
echo.
echo 2. Create a .env file and add:
echo    GROQ_API_KEY=your-api-key-here
echo.
echo 3. Run the application:
echo    python app.py
echo.
echo Or simply double-click start.bat
echo.
pause
