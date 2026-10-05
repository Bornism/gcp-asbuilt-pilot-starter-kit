#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Utility As-Built Quality Firewall - Turnkey GCP Pilot Setup Script
# ==============================================================================
# This script configures all required Google Cloud resources in the Contractor's project:
# 1. Enables required Google Cloud APIs (Cloud Run, Vertex AI, GCS, Cloud Build)
# 2. Creates the Ephemeral Cloud Storage bucket with CORS & 24-Hour TTL Auto-Purge
# 3. Creates the least-privilege Service Account with Vertex AI & GCS permissions
# 4. Uploads the initial externalized rules & reference documents to GCS
# 5. Builds and deploys the container to Google Cloud Run
# ==============================================================================

echo "===================================================================="
echo "⚡ Utility As-Built Quality Firewall - GCP Pilot Provisioning Script"
echo "===================================================================="

# Check for gcloud CLI
if ! command -v gcloud &> /dev/null; then
  echo "❌ Error: 'gcloud' CLI is required. Please install Google Cloud SDK or run from Google Cloud Shell."
  exit 1
fi

# Detect or prompt for Project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "${PROJECT_ID}" ] || [ "${PROJECT_ID}" = "(unset)" ]; then
  read -r -p "Enter your Google Cloud Project ID: " PROJECT_ID
  gcloud config set project "${PROJECT_ID}"
fi

# Configuration Defaults
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SERVICE_NAME="asbuilt-quality-firewall"
BUCKET_NAME="${GCS_BUCKET_NAME:-${PROJECT_ID}-asbuilts}"
SA_NAME="asbuilt-firewall-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"

echo ""
echo "Configuration Parameters:"
echo "--------------------------------------------------------------------"
echo "Project ID:        ${PROJECT_ID}"
echo "Region:            ${REGION}"
echo "Cloud Run Service: ${SERVICE_NAME}"
echo "Storage Bucket:    gs://${BUCKET_NAME}"
echo "Service Account:   ${SA_EMAIL}"
echo "Gemini Model:      ${GEMINI_MODEL}"
echo "--------------------------------------------------------------------"
echo ""

# 1. Enable Required APIs
echo "[1/5] Enabling Google Cloud APIs (Cloud Run, Vertex AI, GCS, Cloud Build)..."
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

# 2. Create Ephemeral GCS Bucket
echo "[2/5] Creating Cloud Storage Bucket with 24-Hour Lifecycle..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
fi

# Apply 24-Hour TTL Auto-Purge Lifecycle
LIFECYCLE_TMP=$(mktemp)
cat << 'EOF' > "${LIFECYCLE_TMP}"
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 1}
    }
  ]
}
EOF
gcloud storage buckets update "gs://${BUCKET_NAME}" --lifecycle-file="${LIFECYCLE_TMP}"
rm -f "${LIFECYCLE_TMP}"

# Apply CORS for Direct PUT Uploads
CORS_TMP=$(mktemp)
cat << 'EOF' > "${CORS_TMP}"
[
  {
    "origin": ["*"],
    "method": ["GET", "PUT", "POST", "HEAD", "OPTIONS"],
    "responseHeader": ["Content-Type", "x-goog-resumable"],
    "maxAgeSeconds": 3600
  }
]
EOF
gcloud storage buckets update "gs://${BUCKET_NAME}" --cors-file="${CORS_TMP}"
rm -f "${CORS_TMP}"

# 3. Upload Rules and Reference Docs to GCS
echo "[3/5] Syncing externalized rules to Cloud Storage..."
if [ -f "config/compliance_rules.yaml" ]; then
  gcloud storage cp config/compliance_rules.yaml "gs://${BUCKET_NAME}/config/compliance_rules.yaml"
fi
if [ -f "config/compliance_rules_template.csv" ]; then
  gcloud storage cp config/compliance_rules_template.csv "gs://${BUCKET_NAME}/config/compliance_rules_template.csv"
fi

# 4. Service Account & IAM Permissions
echo "[4/5] Configuring Least-Privilege Service Account..."
if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Utility As-Built Firewall Service Account"
fi

# Grant Vertex AI user role
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null

# Grant GCS Object Admin on the specific bucket
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" >/dev/null

# 5. Build and Deploy Container to Cloud Run
echo "[5/5] Building and Deploying to Google Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region="${REGION}" \
  --service-account="${SA_EMAIL}" \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},GCS_BUCKET_NAME=${BUCKET_NAME},GEMINI_MODEL=${GEMINI_MODEL},RULES_CONFIG_PATH=gs://${BUCKET_NAME}/config/compliance_rules.yaml,AUTO_PURGE_SOURCE=true"

# Fetch Deployed URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format="value(status.url)")

echo ""
echo "===================================================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "--------------------------------------------------------------------"
echo "Live Service Endpoint: ${SERVICE_URL}"
echo "Swagger API Docs:      ${SERVICE_URL}/docs"
echo "Interactive Pilot UI:  ${SERVICE_URL}/"
echo "Rules Config in GCS:   gs://${BUCKET_NAME}/config/compliance_rules.yaml"
echo "===================================================================="
echo ""
echo "Next Step: Provide '${SERVICE_URL}' to your Power Automate / Azure administrator."
echo "Review PILOT_IMPLEMENTATION_GUIDE.md for step-by-step Power Automate action setup."
