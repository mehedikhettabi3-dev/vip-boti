@echo off
echo ==========================================
echo       VIP BOT AUTO-PUSHER (BY AI)
echo ==========================================
echo.
echo Pushing your latest code and fixes to GitHub...
echo Please wait...
echo.

git add .
git commit -m "Auto-commit: Update API token, fix blinking, clean up admin phone"
git push

echo.
echo ==========================================
echo DONE! The code has been sent to Render.
echo Wait 2 minutes then test the bot.
echo ==========================================
pause
