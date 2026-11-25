@echo off
rem Local development / E2E launcher for the FastAPI backend.
rem The auth rate limit is relaxed here only so the E2E suite can register many users quickly;
rem production uses the default (10/minute) and 429 behaviour is covered by backend tests.
cd /d "%~dp0..backend"
set PYTHONPATH=.
if "%AIRSENSE_RATE_LIMIT_AUTH%"=="" set AIRSENSE_RATE_LIMIT_AUTH=300/minute
if "%AIRSENSE_PYTHON%"=="" set AIRSENSE_PYTHON=python
"%AIRSENSE_PYTHON%" -m uvicorn airsense.app.main:app --port 8000
