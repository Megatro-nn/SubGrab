@echo off
rem Builds dist\SubGrab.exe (portable) and installer\SubGrab-Setup.exe (needs Inno Setup 6).
setlocal
cd /d "%~dp0.."
title Building SubGrab

where python >nul 2>nul
if errorlevel 1 goto nopython

echo [1/5] Installing build tools...
python -m pip install --upgrade pip pyinstaller pillow
if errorlevel 1 goto fail

echo [2/5] Running tests...
python -m unittest discover -s tests
if errorlevel 1 goto fail

echo [3/5] Looking for 7-Zip to bundle (optional, for RAR/7z support)...
if exist "packaging\7zip\7z.exe" goto have7z
if exist "%ProgramFiles%\7-Zip\7z.exe" copy /y "%ProgramFiles%\7-Zip\7z.exe" "packaging\7zip\" >nul
if exist "%ProgramFiles%\7-Zip\7z.dll" copy /y "%ProgramFiles%\7-Zip\7z.dll" "packaging\7zip\" >nul
:have7z
set "HAVE7Z=0"
if exist "packaging\7zip\7z.exe" if exist "packaging\7zip\7z.dll" set "HAVE7Z=1"
echo     bundled 7-Zip: %HAVE7Z%

echo [4/5] Building SubGrab.exe ...
if "%HAVE7Z%"=="1" goto build7z
python -m PyInstaller --noconsole --onedir --clean --noupx --name SubGrab --icon assets\subgrab.ico --version-file packaging\version_info.txt --hidden-import PIL._tkinter_finder subgrab.py
goto built
:build7z
python -m PyInstaller --noconsole --onedir --clean --noupx --name SubGrab --icon assets\subgrab.ico --version-file packaging\version_info.txt --hidden-import PIL._tkinter_finder --add-binary "packaging\7zip\7z.exe;7zip" --add-binary "packaging\7zip\7z.dll;7zip" subgrab.py
:built
if errorlevel 1 goto fail
if not exist "dist\SubGrab\SubGrab.exe" goto fail

if "%SIGN_PFX%"=="" goto nosign
where signtool >nul 2>nul
if errorlevel 1 goto nosigntool
signtool sign /f "%SIGN_PFX%" /p "%SIGN_PASSWORD%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\SubGrab\SubGrab.exe
if errorlevel 1 goto fail
echo     exe signed.
goto nosign
:nosigntool
echo     SIGN_PFX is set but signtool was not found - run this from a "Developer Command Prompt" to sign.
:nosign

echo [5/5] Creating the installer ...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" goto noinno
"%ISCC%" packaging\SubGrab.iss
if errorlevel 1 goto fail

echo.
echo DONE.
echo   Portable app : dist\SubGrab\SubGrab.exe (keep the whole SubGrab folder together)
echo   Installer    : installer\SubGrab-Setup.exe
pause
exit /b 0

:noinno
echo.
echo dist\SubGrab\ was built (SubGrab.exe inside, keep the whole folder together).
echo For the Setup installer, install Inno Setup 6 (free) from https://jrsoftware.org/isdl.php and run this again.
pause
exit /b 0

:nopython
echo Python was not found. Install Python 3.9+ from python.org (tick "Add python.exe to PATH") and run this again.
pause
exit /b 1

:fail
echo.
echo Build failed - scroll up to see the error.
pause
exit /b 1
