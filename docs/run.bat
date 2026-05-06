@echo off
rem Run Sphinx for Windows environments

setlocal
set "FLAGS="
set "DRYRUN=0"

:parse_args
if "%~1"=="" goto run_sphinx

if "%~1"=="-h" goto usage
if "%~1"=="--help" goto usage
if "%~1"=="-n" (
    set "DRYRUN=1"
    shift
    goto parse_args
)
if "%~1"=="--dry-run" (
    set "DRYRUN=1"
    shift
    goto parse_args
)
if "%~1"=="changed" (
    set "FLAGS="
    shift
    goto parse_args
)
if "%~1"=="all" (
    set "FLAGS=-nWa"
    shift
    goto parse_args
)

echo Error: invalid argument '%~1'
goto usage

:usage
echo usage: %~nx0 [options] [MODE]
echo  options: %~nx0 [-h^|--help] [-n^|--dry-run] [MODE]
echo    -h^|--help    : Print this message
echo    -n^|--dry-run : Print command, don't run it
echo  values for MODE:
echo    changed : Only regenerate changed files [default]
echo    all     : Regenerate all files
exit /b 0

:run_sphinx
if "%DRYRUN%"=="1" (
    echo sphinx-build %FLAGS% -w sphinx.out . build
) else (
    sphinx-build %FLAGS% -w sphinx.out . build
)
