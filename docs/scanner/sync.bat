@echo off
:: mrx sync - runs on the scanner PC, next to the Pulseq interpreter.
:: See docs/scan/scanner-setup.md in the mcp-gateway repo.
::
:: Every round (about 3 s):
::   1. inbox  : every .seq in V:\inbox (oldest name first) is copied to the
::               scanner's dated folder, appended to control.txt in front of the
::               trailing "wait", and moved to V:\measurement\<date> as a record.
::   2. results: every finished .seq.dat on the scanner is moved to the same
::               dated folder on the share. It shows up there under its real name
::               only once it is complete.
::   3. status : control.txt, position.txt and a heartbeat are copied to
::               V:\status, so the PC with the script knows what the scanner does.
::
:: Start this BEFORE the Pulseq interpreter (or while it is stopped): it archives
:: control.txt and starts a fresh one with position 0.
:: Stop with CTRL+C.
::
:: Usage: sync.bat [share] [pulseq folder]
::   share         : the share as the scanner PC sees it        (generic default V:)
::   pulseq folder : the interpreter's folder, with seq-files\measurement and
::                   control below it  (generic default: the Siemens CustomerSeq\pulseq)
:: What is given is remembered in the user environment variables MRX_SYNC_SHARE
:: and MRX_SYNC_PULSEQ and used on the next start. Order: argument, variable,
:: generic default.

setlocal EnableExtensions DisableDelayedExpansion
title mrx sync

:: --- Paths ------------------------------------------------------------------
set "SHARE=V:"
if defined MRX_SYNC_SHARE set "SHARE=%MRX_SYNC_SHARE%"
if not "%~1"=="" set "SHARE=%~1"
if "%SHARE:~-1%"=="\" set "SHARE=%SHARE:~0,-1%"
set "PULSEQ=C:\ProgramData\Siemens\Numaris\MriCustomer\CustomerSeq\pulseq"
if defined MRX_SYNC_PULSEQ set "PULSEQ=%MRX_SYNC_PULSEQ%"
if not "%~2"=="" set "PULSEQ=%~2"
if "%PULSEQ:~-1%"=="\" set "PULSEQ=%PULSEQ:~0,-1%"

:: No parentheses around paths here: a ")" in a path would end the block
if not exist "%SHARE%\" goto no_share
if not exist "%PULSEQ%\control\" goto no_pulseq
:: Remember what worked for the next start (setx: new consoles see it)
if /i not "%MRX_SYNC_SHARE%"=="%SHARE%" setx MRX_SYNC_SHARE "%SHARE%" >nul
if /i not "%MRX_SYNC_PULSEQ%"=="%PULSEQ%" setx MRX_SYNC_PULSEQ "%PULSEQ%" >nul

set "INBOX=%SHARE%\inbox"
set "STATUS=%SHARE%\status"
set "NET_ROOT=%SHARE%\measurement"
set "HOST_ROOT=%PULSEQ%\seq-files\measurement"
set "HOST_CONTROL=%PULSEQ%\control"
set "CONTROL=%HOST_CONTROL%\control.txt"
set "POSITION=%HOST_CONTROL%\position.txt"

:: --- Start: fresh control.txt ------------------------------------------------
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "RUN=%%i"
for %%d in ("%INBOX%" "%STATUS%" "%NET_ROOT%" "%HOST_CONTROL%\archive") do if not exist "%%~d" mkdir "%%~d"

if exist "%CONTROL%" copy /Y "%CONTROL%" "%HOST_CONTROL%\archive\control-%RUN%.txt" >nul
:: control.txt first: a position of 0 with the old list would measure it again
> "%CONTROL%" echo wait
echo 0 > "%POSITION%"

set "BEAT=0"
call :log started, run %RUN%, share %SHARE%, pulseq %PULSEQ%, control.txt reset (old one in %HOST_CONTROL%\archive)

:loop
:: The date is taken every round, so a session that runs past midnight
:: carries on in the new day's folder.
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"
set "HOST_DAY=%HOST_ROOT%\%TODAY%"
set "NET_DAY=%NET_ROOT%\%TODAY%"
if not exist "%HOST_DAY%" mkdir "%HOST_DAY%"
if not exist "%NET_DAY%" mkdir "%NET_DAY%"

:: 1) Inbox -> scanner, in name order (the script names files by drop time)
for /f "delims=" %%F in ('dir /b /a-d /on "%INBOX%\*.seq" 2^>nul') do call :schedule "%%F"

:: 2) Results -> share. Only today's folder is searched; other date folders
::    are left alone.
call :collect %TODAY%

:: 3) Status for the script
set /a BEAT+=1
call :publish "%CONTROL%" control.txt
call :publish "%POSITION%" position.txt
> "%STATUS%\heartbeat.txt.tmp" echo %RUN% %BEAT% %TODAY%
move /Y "%STATUS%\heartbeat.txt.tmp" "%STATUS%\heartbeat.txt" >nul

timeout /t 2 /nobreak >nul
goto loop


:: --- Subroutines -------------------------------------------------------------

:schedule
:: %1: file name in the inbox
set "NAME=%~1"
:: Already in control.txt (sync was stopped between appending and moving)?
:: Then only finish the move, never append twice.
findstr /I /L /C:"%NAME%" "%CONTROL%" >nul && goto schedule_done
copy /Y "%INBOX%\%NAME%" "%HOST_DAY%\%NAME%" >nul || (call :log could not copy %NAME% to the scanner & exit /b)
call :append "%HOST_DAY%\%NAME%"
call :log scheduled %NAME%
:schedule_done
move /Y "%INBOX%\%NAME%" "%NET_DAY%\%NAME%" >nul
exit /b

:append
:: %1: path to put in front of the trailing "wait". Every other line stays
:: exactly as it is (blank ones too): the interpreter counts lines.
set "N=0"
for /f %%n in ('type "%CONTROL%" ^| find /c /v ""') do set "N=%%n"
> "%CONTROL%.tmp" (
    for /f "tokens=1* delims=:" %%a in ('findstr /n "^" "%CONTROL%"') do (
        if %%a lss %N% (
            echo(%%b
        ) else if /i not "%%b"=="wait" (
            echo(%%b
        )
    )
    echo(%~1
    echo wait
)
move /Y "%CONTROL%.tmp" "%CONTROL%" >nul
exit /b

:collect
:: %1: date folder (yyyyMMdd). Moves finished .dat files from the scanner's
:: folder of that day to the same folder on the share. The rename fails while
:: the ICE program still writes the file; then it is taken in a later round.
set "SRC=%HOST_ROOT%\%~1"
set "DST=%NET_ROOT%\%~1"
if not exist "%SRC%" exit /b
:: Already on the share = measured again, the data is there: delete it on the
:: scanner instead of copying it again.
for /r "%SRC%" %%F in (*.dat) do call :dedupe "%%F"
for /r "%SRC%" %%F in (*.dat) do ren "%%F" "%%~nxF.tmp" 2>nul
robocopy "%SRC%" "%DST%" *.dat.tmp /S /MOV /IS /FFT /Z /R:2 /W:2 /NJH /NJS /NDL /NFL /NP >nul
if errorlevel 8 (
    call :log copying results of %~1 to the share failed, trying again next round
    exit /b
)
:: If the .dat is already there, the .tmp is a duplicate: delete it.
if exist "%DST%" for /r "%DST%" %%F in (*.dat.tmp) do (
    if exist "%%~dpnF" (
        del /F /Q "%%F" 2>nul && call :log %%~nF already on the share, deleted the duplicate .tmp
    ) else (
        ren "%%F" "%%~nF" 2>nul && call :log result %%~nF
    )
)
exit /b

:dedupe
:: %1: .dat on the scanner. If the same file (same path below the date folder)
:: is already on the share, delete the one on the scanner. Fails while the ICE
:: program still writes it; then it is deleted in a later round.
set "F=%~1"
call set "T=%%F:%SRC%=%DST%%%"
if exist "%T%" del /F /Q "%F%" 2>nul && call :log %~nx1 already on the share, deleted it on the scanner
exit /b

:publish
:: %1: file to copy, %2: name in the status folder. Copied, then renamed, so
:: the script never reads half a file.
copy /Y "%~1" "%STATUS%\%~2.tmp" >nul 2>&1 && move /Y "%STATUS%\%~2.tmp" "%STATUS%\%~2" >nul
exit /b

:log
echo [%date% %time:~0,8%] %*
>> "%STATUS%\sync.log" echo [%date% %time:~0,8%] %*
exit /b

:no_share
echo Share not found: %SHARE%
echo Start it as: sync.bat ^<share^> [pulseq folder]   - both are remembered.
pause
exit /b 1

:no_pulseq
echo No control folder in the Pulseq folder %PULSEQ%
echo Start it as: sync.bat ^<share^> ^<pulseq folder^>   - both are remembered.
pause
exit /b 1
