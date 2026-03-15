#!/bin/bash
# Todo Calendar App Health Check
# Probes key endpoints and logs results in cron.log format
# Called by launchd every 3 hours

LOG_DIR="/Users/gtsiamis/Claude/TodoCalendarApp_Health/logs"
LOG_FILE="$LOG_DIR/cron.log"
BASE_URL="https://gtsiamis-precision-workstation-t5400.tail48a912.ts.net:8443"
TIMEOUT=15

mkdir -p "$LOG_DIR"

START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "======================================" >> "$LOG_FILE"
echo "Started: $START_TIME" >> "$LOG_FILE"

EXIT_CODE=0
RESULTS=""

# 1. Nginx health check
HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' --max-time $TIMEOUT "$BASE_URL/health" 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    RESULTS+="[OK] Nginx: responding (HTTP $HTTP_CODE)"$'\n'
else
    RESULTS+="[FAIL] Nginx: HTTP $HTTP_CODE"$'\n'
    EXIT_CODE=1
fi

# 2. Backend API health check
BACKEND_RESP=$(curl -sk --max-time $TIMEOUT "$BASE_URL/api/health" 2>/dev/null)
BACKEND_CODE=$?
if [ $BACKEND_CODE -eq 0 ] && echo "$BACKEND_RESP" | grep -q '"status":"ok"'; then
    RESULTS+="[OK] Backend API: healthy"$'\n'
else
    RESULTS+="[FAIL] Backend API: not responding or unhealthy"$'\n'
    EXIT_CODE=1
fi

# 3. Google Calendar auth status
CAL_RESP=$(curl -sk --max-time $TIMEOUT "$BASE_URL/api/v1/calendar/auth/status" 2>/dev/null)
CAL_CODE=$?
if [ $CAL_CODE -eq 0 ]; then
    if echo "$CAL_RESP" | grep -q '"authenticated":true'; then
        RESULTS+="[OK] Google Calendar: authenticated"$'\n'
    else
        RESULTS+="[WARN] Google Calendar: not authenticated"$'\n'
    fi
else
    RESULTS+="[FAIL] Google Calendar: endpoint unreachable"$'\n'
    EXIT_CODE=1
fi

# 4. Email service status
EMAIL_RESP=$(curl -sk --max-time $TIMEOUT "$BASE_URL/api/v1/email/status" 2>/dev/null)
EMAIL_CODE=$?
if [ $EMAIL_CODE -eq 0 ]; then
    if echo "$EMAIL_RESP" | grep -q '"configured":true'; then
        RESULTS+="[OK] Email service: configured"$'\n'
    else
        RESULTS+="[WARN] Email service: not configured"$'\n'
    fi
else
    RESULTS+="[FAIL] Email service: endpoint unreachable"$'\n'
    EXIT_CODE=1
fi

# 5. Frontend check (index.html loads)
FRONT_CODE=$(curl -sk -o /dev/null -w '%{http_code}' --max-time $TIMEOUT "$BASE_URL/" 2>/dev/null)
if [ "$FRONT_CODE" = "200" ]; then
    RESULTS+="[OK] Frontend: serving (HTTP $FRONT_CODE)"$'\n'
else
    RESULTS+="[FAIL] Frontend: HTTP $FRONT_CODE"$'\n'
    EXIT_CODE=1
fi

# Write results
echo "$RESULTS" >> "$LOG_FILE"

END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "Completed: $END_TIME (exit code: $EXIT_CODE)" >> "$LOG_FILE"

exit $EXIT_CODE
