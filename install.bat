@echo off
REM ============================================
REM  Install dependencies (only 1x)
REM ============================================
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Installation complete!
pause
