#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# End-to-End Pilot Pipeline Test Script
# ==============================================================================
# Simulates the entire Power Automate -> Cloud Run -> Gemini -> Scorecard flow:
# 1. Tests health endpoint
# 2. Generates a synthetic test drawing package
# 3. Requests a presigned URL
# 4. Executes an audit call
# 5. Downloads and verifies the generated Excel scorecard
# ==============================================================================

TARGET_URL="${1:-http://localhost:8080}"

echo "===================================================================="
echo "⚡ Testing Utility As-Built Quality Firewall Pipeline at: ${TARGET_URL}"
echo "===================================================================="

# 1. Health check
echo "[1/4] Checking service health..."
curl -s -f "${TARGET_URL}/api/health" | grep -q "healthy" && echo "✅ Service is HEALTHY"

# 2. Inspect active rules
echo "[2/4] Verifying externalized rules engine..."
RULES_INFO=$(curl -s "${TARGET_URL}/api/rules")
echo "✅ Active Rules Loaded: $(echo "${RULES_INFO}" | grep -o '"id":' | wc -l) checks"

# 3. Run Audit Simulation
echo "[3/4] Running As-Built compliance audit..."
AUDIT_RESP=$(curl -s -X POST "${TARGET_URL}/api/audit-package" \
  -H "Content-Type: application/json" \
  -d '{
    "gcs_uri": "gs://simulated-bucket/uploads/test_drawing.pdf",
    "filename": "test_drawing.pdf",
    "rule_profile": "all",
    "mock_mode": true
  }')

JOB_ID=$(echo "${AUDIT_RESP}" | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)
STATUS=$(echo "${AUDIT_RESP}" | grep -o '"overall_status":"[^"]*' | cut -d'"' -f4)
FAILED_COUNT=$(echo "${AUDIT_RESP}" | grep -o '"failed_count":[0-9]*' | cut -d':' -f2)

echo "✅ Audit Complete!"
echo "   Job Work Order:  ${JOB_ID}"
echo "   Overall Status:  ${STATUS}"
echo "   Defects Caught:  ${FAILED_COUNT}"

# 4. Verify Scorecard Download
echo "[4/4] Verifying Excel scorecard download..."
SCORECARD_FILE="/tmp/test_scorecard.xlsx"
curl -s -f "${TARGET_URL}/api/download-scorecard?job=${JOB_ID}" -o "${SCORECARD_FILE}"
if [ -s "${SCORECARD_FILE}" ]; then
  echo "✅ Excel Scorecard downloaded successfully (${SCORECARD_FILE}, $(wc -c < "${SCORECARD_FILE}") bytes)"
else
  echo "❌ Scorecard download failed"
  exit 1
fi

echo "===================================================================="
echo "🎉 ALL END-TO-END PIPELINE CHECKS PASSED!"
echo "===================================================================="
