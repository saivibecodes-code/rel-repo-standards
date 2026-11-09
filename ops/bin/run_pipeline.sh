#!/usr/bin/env bash
# ==============================================================================
# rel-* Automated Pipeline Execution Harness with Health Check and Alerting
# ==============================================================================
set -euo pipefail

REPO_NAME="${1:-rel-aly-works}"
BASE_DIR="${2:-/home/ubuntu}"
REPO_DIR="${BASE_DIR}/${REPO_NAME}"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

echo "=============================================================================="
echo "[*] RUNNING PIPELINE: ${REPO_NAME} at ${TIMESTAMP}"
echo "[*] Working Directory: ${REPO_DIR}"
echo "=============================================================================="

if [ ! -d "${REPO_DIR}" ]; then
    echo "[!] ERROR: Directory ${REPO_DIR} does not exist!"
    exit 1
fi

cd "${REPO_DIR}"

# 1. Check for Virtual Environment
PYTHON_BIN=".venv/bin/python3"
if [ ! -f "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

# 2. Execute Pipeline
START_TIME=$(date +%s)
echo "[*] Launching run_all.py..."

if ${PYTHON_BIN} run_all.py; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo "[✓] Pipeline ${REPO_NAME} completed successfully in ${DURATION}s."

    # 3. Write success metadata
    mkdir -p monitoring
    cat <<EOF > monitoring/last_success.json
{
  "pipeline": "${REPO_NAME}",
  "status": "SUCCESS",
  "timestamp": "${TIMESTAMP}",
  "duration_seconds": ${DURATION}
}
EOF
    exit 0
else
    STATUS=$?
    echo "[✗] Pipeline ${REPO_NAME} FAILED with status code ${STATUS}!"
    mkdir -p monitoring
    cat <<EOF > monitoring/last_failure.json
{
  "pipeline": "${REPO_NAME}",
  "status": "FAILED",
  "exit_code": ${STATUS},
  "timestamp": "${TIMESTAMP}"
}
EOF
    exit ${STATUS}
fi
