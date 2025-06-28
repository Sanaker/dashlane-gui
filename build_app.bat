@echo off
echo Starting the Dashlane GUI executable build process...
pyinstaller --noconfirm --onefile --windowed --icon "bilde.png" --add-data "bilde.png;." "main.py"
if %errorlevel% equ 0 (
    echo.
    echo Build completed successfully!
    echo The executable can be found in the "dist" folder.
) else (
    echo.
    echo An error occurred during the build process. Please check the output above.
)
echo.
pause