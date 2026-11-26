@echo off
:: mrx sync - runs on the scanner PC, next to the Pulseq interpreter.
:: See docs/scan/scanner-setup.md in the mcp-gateway repo.
::
:: Every round (about 3 s):
::   1. inbox  : every .seq in V:\inbox (oldest name first) is copied to the
::               scanner's dated folder, appended to control.txt in front of the
::               trailing "wait", and moved to V:\measurement\<date> as a record.
::   2. results: every measured job whose <name>.seq.done is there is moved,
::               as a set, to the same dated folder on the share:
::               <name>.seq.npy and <name>.seq.scans.npy first, the .seq.done
::               last. A set on the share is complete once its .seq.done is.
::               Today's and yesterday's folder are searched (a job measured
::               just before midnight leaves its set in yesterday's).
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
:: generic default. At start it prints the command with every setting typed in.

setlocal EnableExtensions DisableDelayedExpansion
title mrx sync

:: --- Paths ------------------------------------------------------------------
set "SHARE=V:"
set "SHARE_FROM=the generic default, nothing remembered in MRX_SYNC_SHARE yet"
if defined MRX_SYNC_SHARE set "SHARE=%MRX_SYNC_SHARE%"
if defined MRX_SYNC_SHARE set "SHARE_FROM=remembered in MRX_SYNC_SHARE"
if not "%~1"=="" set "SHARE=%~1"
if not "%~1"=="" set "SHARE_FROM=given as the 1st argument"
if "%SHARE:~-1%"=="\" set "SHARE=%SHARE:~0,-1%"
set "PULSEQ=C:\ProgramData\Siemens\Numaris\MriCustomer\CustomerSeq\pulseq"
set "PULSEQ_FROM=the generic default, nothing remembered in MRX_SYNC_PULSEQ yet"
if defined MRX_SYNC_PULSEQ set "PULSEQ=%MRX_SYNC_PULSEQ%"
if defined MRX_SYNC_PULSEQ set "PULSEQ_FROM=remembered in MRX_SYNC_PULSEQ"
if not "%~2"=="" set "PULSEQ=%~2"
if not "%~2"=="" set "PULSEQ_FROM=given as the 2nd argument"
if "%PULSEQ:~-1%"=="\" set "PULSEQ=%PULSEQ:~0,-1%"

:: No parentheses around paths here: a ")" in a path would end the block
if not exist "%SHARE%\" goto no_share
if not exist "%PULSEQ%\control\" goto no_pulseq
:: Remember what worked for the next start (setx: new consoles see it)
if /i not "%MRX_SYNC_SHARE%"=="%SHARE%" setx MRX_SYNC_SHARE "%SHARE%" >nul
if /i not "%MRX_SYNC_PULSEQ%"=="%PULSEQ%" setx MRX_SYNC_PULSEQ "%PULSEQ%" >nul
set "COMMAND=sync.bat "%SHARE%" "%PULSEQ%""
echo.
echo Next time, the same settings are:
echo   %COMMAND%
echo.

set "INBOX=%SHARE%\inbox"
set "STATUS=%SHARE%\status"
set "NET_ROOT=%SHARE%\measurement"
set "HOST_ROOT=%PULSEQ%\seq-files\measurement"
set "HOST_CONTROL=%PULSEQ%\control"
set "CONTROL=%HOST_CONTROL%\control.txt"
set "POSITION=%HOST_CONTROL%\position.txt"
:: Data the sequence could not give to any line (ExportedData.unassigned.*):
:: reported, never collected
set "HOST_DATA=%PULSEQ%\data"
set "UNASSIGNED_SEEN="

:: --- Start: fresh control.txt ------------------------------------------------
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "RUN=%%i"
for %%d in ("%INBOX%" "%STATUS%" "%NET_ROOT%" "%HOST_CONTROL%\archive") do if not exist "%%~d" mkdir "%%~d"

if exist "%CONTROL%" copy /Y "%CONTROL%" "%HOST_CONTROL%\archive\control-%RUN%.txt" >nul
:: control.txt first: a position of 0 with the old list would measure it again
> "%CONTROL%" echo wait
echo 0 > "%POSITION%"

set "BEAT=0"
call :log started, run %RUN%, control.txt reset (old one in %HOST_CONTROL%\archive)
call :log same settings next time: %COMMAND%

:loop
:: The date is taken every round, so a session that runs past midnight
:: carries on in the new day's folder.
set "TODAY="
set "YESTERDAY="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd; Get-Date (Get-Date).AddDays(-1) -Format yyyyMMdd"') do (
    if not defined TODAY (set "TODAY=%%i") else set "YESTERDAY=%%i"
)
set "HOST_DAY=%HOST_ROOT%\%TODAY%"
set "NET_DAY=%NET_ROOT%\%TODAY%"
if not exist "%HOST_DAY%" mkdir "%HOST_DAY%"
if not exist "%NET_DAY%" mkdir "%NET_DAY%"

:: 1) Inbox -> scanner, in name order (the script names files by drop time)
for /f "delims=" %%F in ('dir /b /a-d /on "%INBOX%\*.seq" 2^>nul') do call :schedule "%%F"

:: 2) Results -> share. Only today's and yesterday's folders are searched;
::    older date folders are left alone.
call :collect %YESTERDAY%
call :collect %TODAY%
call :unassigned

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
:: %1: date folder (yyyyMMdd). Moves every finished set from the scanner's
:: folder of that day to the same folder on the share. A set is finished once
:: the sequence has put its .seq.done next to it (it moves that one last).
set "SRC=%HOST_ROOT%\%~1"
set "DST=%NET_ROOT%\%~1"
if not exist "%SRC%" exit /b
for /r "%SRC%" %%F in (*.seq.done) do call :collect_set "%%F"
exit /b

:collect_set
:: %1: <name>.seq.done on the scanner. Moves <name>.seq.npy and .scans.npy (a
:: job without ADCs has none), then the .done. Anything that fails is tried
:: again next round: the .done stays on the scanner until it is on the share.
set "BASE=%~dpn1"
set "SET_NAME=%~n1"
set "SET_DIR=%~dp1"
call set "T=%%BASE:%SRC%=%DST%%%"
for %%T in ("%T%") do set "T_DIR=%%~dpT"
set "STATUS_WORD=?"
for /f "usebackq tokens=1,2" %%a in ("%~1") do if /i "%%a"=="status" set "STATUS_WORD=%%b"
:: Already on the share = measured again, the data is there: delete the set
:: on the scanner instead of copying it again.
:: (No parenthesized blocks below: a ")" in a name would end them.)
if exist "%T%.done" goto collect_set_duplicate
if not exist "%T_DIR%" mkdir "%T_DIR%"
robocopy "%SET_DIR:~0,-1%" "%T_DIR:~0,-1%" "%SET_NAME%.npy" "%SET_NAME%.scans.npy" /MOV /IS /Z /R:2 /W:2 /NJH /NJS /NDL /NFL /NP >nul
if errorlevel 8 goto collect_set_failed
if exist "%BASE%.npy" goto collect_set_wait
if exist "%BASE%.scans.npy" goto collect_set_wait
:: The .done last, under a temporary name, so the script never reads half of it
copy /Y "%~1" "%T%.done.tmp" >nul 2>&1 || goto collect_set_wait
move /Y "%T%.done.tmp" "%T%.done" >nul || goto collect_set_wait
del /F /Q "%~1" 2>nul
call :log result %SET_NAME% (%STATUS_WORD%)
exit /b
:collect_set_wait
call :log %SET_NAME% not completely on the share yet, trying again next round
exit /b
:collect_set_failed
call :log copying %SET_NAME% to the share failed, trying again next round
exit /b
:collect_set_duplicate
del /F /Q "%BASE%.npy" "%BASE%.scans.npy" 2>nul
del /F /Q "%~1" 2>nul && call :log %SET_NAME% already on the share, deleted it on the scanner
exit /b

:unassigned
:: Reports ExportedData.unassigned.* in the interpreter's data folder once:
:: data the sequence could not give to any line (a measurement repeated after
:: a timeout, a manual one). It is not collected.
:: No parentheses around paths here: a ")" in a path would end the block
if not exist "%HOST_DATA%\ExportedData.unassigned.*" set "UNASSIGNED_SEEN="
if not exist "%HOST_DATA%\ExportedData.unassigned.*" exit /b
if defined UNASSIGNED_SEEN exit /b
set "UNASSIGNED_SEEN=1"
call :log data that belongs to no job is in %HOST_DATA%: ExportedData.unassigned.*, not collected
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
echo The share is %SHARE_FROM%.
echo Start it as: sync.bat ^<share^> [pulseq folder]   - both are remembered.
pause
exit /b 1

:no_pulseq
echo No control folder in the Pulseq folder %PULSEQ%
echo The Pulseq folder is %PULSEQ_FROM%.
echo Start it as: sync.bat ^<share^> ^<pulseq folder^>   - both are remembered.
pause
exit /b 1
