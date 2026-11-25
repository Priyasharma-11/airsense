#!/usr/bin/env sh
# Local development / E2E launcher for the API (macOS / Linux / Git Bash)
cd "$(dirname "$0")/../backend" || exit 1
export PYTHONPATH=.
export AIRSENSE_RATE_LIMIT_AUTH="${AIRSENSE_RATE_LIMIT_AUTH:-300/minute}"   # relaxed for E2E only
exec "${AIRSENSE_PYTHON:-python}" -m uvicorn airsense.app.main:app --port 8000 --reload
