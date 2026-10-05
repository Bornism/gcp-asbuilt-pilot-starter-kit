"""
FastAPI Cloud Run Service: Utility As-Built Quality Firewall
============================================================
Middleware microservice handling:
1. Presigned V4 Upload URLs (bypasses Power Automate 100MB buffer ceilings).
2. Pure Gemini Flash Multimodal Audit (Vertex AI with Context Caching & schema enforcement).
3. In-memory Excel Scorecard generation (.xlsx via openpyxl in ~250ms).
4. Zero-Residue source PDF auto-purge.
5. Externalized rules and profile management.
"""

import os
import io
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage

from app.schemas import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    AuditRequest,
    AuditResponse,
    JobPackageAuditReport
)
from app.rules_loader import RulesEngine
from app.scorecard_builder import generate_excel_scorecard
from app.evaluator import MultimodalAuditEvaluator

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("asbuilt-firewall-api")

# Environment & GCP Settings
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("PROJECT_ID", "your-gcp-project"))
REGION = os.getenv("GOOGLE_CLOUD_REGION", os.getenv("REGION", "us-central1"))
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", f"{PROJECT_ID}-asbuilts")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
AUTO_PURGE_DEFAULT = os.getenv("AUTO_PURGE_SOURCE", "true").lower() == "true"
RULES_CONFIG_PATH = os.getenv("RULES_CONFIG_PATH", "config/compliance_rules.yaml")

# Initialize Storage & Engines
try:
    storage_client = storage.Client(project=PROJECT_ID)
    logger.info(f"Initialized Cloud Storage client for project: {PROJECT_ID}")
except Exception as e:
    logger.warning(f"Could not initialize Cloud Storage client: {e}. Running in local/mock mode.")
    storage_client = None

rules_engine = RulesEngine(config_path=RULES_CONFIG_PATH, storage_client=storage_client)
evaluator = MultimodalAuditEvaluator(
    project_id=PROJECT_ID,
    region=REGION,
    bucket_name=BUCKET_NAME,
    model_name=MODEL_NAME,
    rules_engine=rules_engine,
    storage_client=storage_client
)

app = FastAPI(
    title="Utility As-Built Quality Firewall",
    description="Automated Multimodal Pre-Submission Audit for Utility Drawing Packages via Google Cloud Vertex AI",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Service health and runtime configuration check."""
    return {
        "status": "healthy",
        "service": "Utility As-Built Quality Firewall",
        "project": PROJECT_ID,
        "region": REGION,
        "bucket": BUCKET_NAME,
        "model": MODEL_NAME,
        "rules_version": rules_engine.version,
        "active_rules_count": len(rules_engine.rules),
        "available_profiles": list(rules_engine.profiles.keys())
    }


@app.post("/api/generate-presigned-url", response_model=PresignedUrlResponse)
def generate_presigned_url(req: PresignedUrlRequest):
    """
    Mints a GCS V4 Presigned PUT URL.
    Power Automate / SharePoint streams large CAD PDFs (30MB to 150MB+) directly into
    GCS using this URL, completely bypassing Power Automate payload and memory limits.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    clean_filename = os.path.basename(req.filename).replace(" ", "_")
    blob_name = f"uploads/{timestamp}_{clean_filename}"
    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"

    if storage_client:
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(blob_name)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),
                method="PUT",
                content_type=req.content_type
            )
            logger.info(f"Generated V4 Presigned PUT URL for blob: {blob_name}")
            return PresignedUrlResponse(upload_url=url, gcs_uri=gcs_uri, blob_name=blob_name)
        except Exception as e:
            logger.warning(f"Failed to generate live GCS signed URL: {e}. Falling back to simulation URL.")

    simulated_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}?X-Goog-Algorithm=GOOG4-RSA-SHA256&simulated=true"
    return PresignedUrlResponse(upload_url=simulated_url, gcs_uri=gcs_uri, blob_name=blob_name)


@app.post("/api/audit-package", response_model=AuditResponse)
def audit_package(req: AuditRequest, background_tasks: BackgroundTasks):
    """
    Core Evaluation Endpoint:
    1. Audits PDF via Vertex AI Gemini Flash against externalized rules.
    2. Builds color-coded Excel scorecard in memory via openpyxl.
    3. Deposits scorecard into GCS and generates signed download URL.
    4. Auto-purges source PDF (Zero-Residue policy) if configured.
    """
    logger.info(f"Auditing package: {req.gcs_uri} with profile '{req.rule_profile}'")

    # 1. Evaluate package with Gemini Flash
    report = evaluator.audit_package(
        gcs_uri=req.gcs_uri,
        rule_profile=req.rule_profile,
        selected_rule_ids=req.selected_rule_ids,
        mock_mode=req.mock_mode or (storage_client is None)
    )

    # 2. Generate Excel Scorecard (.xlsx)
    excel_bytes = generate_excel_scorecard(report)
    scorecard_filename = f"Scorecard_{report.utility_work_order}.xlsx"
    scorecard_blob = f"scorecards/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{scorecard_filename}"
    download_url = f"/api/download-scorecard?job={report.utility_work_order}"

    # 3. Save Scorecard to GCS
    if storage_client:
        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(scorecard_blob)
            blob.upload_from_string(
                excel_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            download_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=24),
                method="GET"
            )
        except Exception as e:
            logger.warning(f"Could not upload scorecard to GCS: {e}")

    # Local fallback buffer
    os.makedirs("/tmp/scorecards", exist_ok=True)
    with open(f"/tmp/scorecards/{report.utility_work_order}.xlsx", "wb") as f:
        f.write(excel_bytes)

    # 4. Zero-Residue Auto-Purge of CAD source drawing
    source_purged = False
    should_purge = req.auto_purge_source if req.auto_purge_source is not None else AUTO_PURGE_DEFAULT
    if should_purge and storage_client and req.gcs_uri.startswith("gs://"):
        try:
            parts = req.gcs_uri.replace("gs://", "").split("/", 1)
            if len(parts) == 2:
                src_bucket, src_blob = parts[0], parts[1]
                b = storage_client.bucket(src_bucket)
                target_blob = b.blob(src_blob)
                if target_blob.exists():
                    target_blob.delete()
                    source_purged = True
                    logger.info(f"Zero-Residue: Auto-purged source PDF {req.gcs_uri}")
        except Exception as pe:
            logger.warning(f"Could not auto-purge source PDF {req.gcs_uri}: {pe}")

    return AuditResponse(
        job_id=report.utility_work_order,
        overall_status=report.overall_compliance_status,
        compliance_score_pct=report.compliance_score_pct,
        total_checks=report.total_checks,
        failed_count=report.failed_count,
        scorecard_filename=scorecard_filename,
        scorecard_download_url=download_url,
        gcs_scorecard_uri=f"gs://{BUCKET_NAME}/{scorecard_blob}",
        source_purged=source_purged,
        report=report
    )


@app.get("/api/download-scorecard")
def download_scorecard(job: str):
    """Direct HTTP download endpoint for locally cached scorecards."""
    file_path = f"/tmp/scorecards/{job}.xlsx"
    if os.path.exists(file_path):
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"Scorecard_{job}.xlsx"
        )
    raise HTTPException(status_code=404, detail="Scorecard not found or expired.")


@app.get("/api/rules")
def get_rules():
    """Returns the externalized compliance rules catalog and active profiles."""
    return {
        "version": rules_engine.version,
        "last_updated": rules_engine.last_updated,
        "rules": rules_engine.rules,
        "profiles": rules_engine.profiles
    }


@app.post("/api/rules/reload")
def reload_rules():
    """Reloads the rules and profiles from GCS or local configuration file."""
    rules_engine.load_rules()
    return {
        "status": "reloaded",
        "rules_count": len(rules_engine.rules),
        "profiles_count": len(rules_engine.profiles),
        "config_path": rules_engine.config_path
    }


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    """Interactive Customer Dashboard for Live Demonstration."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Utility As-Built Quality Firewall - Pilot Console</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
  </style>
</head>
<body class="min-h-screen text-slate-800">
  <header class="bg-white border-b border-slate-200 px-8 py-4 sticky top-0 z-50 shadow-sm">
    <div class="max-w-7xl mx-auto flex justify-between items-center">
      <div class="flex items-center space-x-3">
        <div class="h-10 w-10 bg-blue-600 rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-md shadow-blue-500/20">
          <i class="fa-solid fa-bolt"></i>
        </div>
        <div>
          <h1 class="text-base font-bold text-slate-900 tracking-tight">Utility As-Built Quality Firewall</h1>
          <p class="text-xs text-slate-500">Google Cloud Vertex AI (Gemini Flash) • Pilot Starter Kit</p>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <a href="/docs" target="_blank" class="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50">
          <i class="fa-solid fa-book mr-1"></i> Swagger OpenAPI Docs
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-8 py-8 space-y-6">
    <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <h2 class="text-lg font-bold text-slate-900 mb-2">Simulate Pre-Submission Audit</h2>
      <p class="text-sm text-slate-600 mb-6">
        Simulate an incoming As-Built job package from SharePoint / Power Automate. The pipeline evaluates the document against all active rules, checks for missing PE stamps, reconciles plan footage vs BOM tallies, and generates an openpyxl Excel scorecard.
      </p>

      <div class="flex flex-wrap gap-4 items-center mb-6">
        <button onclick="runAudit(true)" id="audit-btn" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-xl shadow-md transition-all flex items-center text-sm">
          <i class="fa-solid fa-play mr-2"></i> Run Benchmark Package Audit
        </button>
        <span class="text-xs text-slate-400">or</span>
        <button onclick="fetchRules()" class="border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold px-4 py-2.5 rounded-xl transition-all text-sm">
          <i class="fa-solid fa-list-check mr-2"></i> Inspect Active Rules Catalog
        </button>
      </div>

      <div id="loading" class="hidden text-sm text-blue-600 flex items-center mb-4">
        <i class="fa-solid fa-circle-notch fa-spin mr-2"></i> Auditing 17 rules with Vertex AI Gemini Flash...
      </div>

      <div id="results" class="hidden space-y-4">
        <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 flex justify-between items-center">
          <div>
            <span id="res-status" class="px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800">STATUS</span>
            <span id="res-score" class="ml-3 text-sm font-semibold text-slate-700">Score: 88.2%</span>
            <p id="res-workorder" class="text-xs text-slate-500 mt-1">Work Order: WO-440219-FRESNO</p>
          </div>
          <a id="res-download" href="#" target="_blank" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm flex items-center">
            <i class="fa-solid fa-file-excel mr-1.5"></i> Download Excel Scorecard (.xlsx)
          </a>
        </div>
        <div class="overflow-x-auto border border-slate-200 rounded-xl">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-100 text-slate-700 uppercase font-semibold">
              <tr>
                <th class="p-3">#</th>
                <th class="p-3">Rule Name</th>
                <th class="p-3">Status</th>
                <th class="p-3">PDF Page</th>
                <th class="p-3">Sheet #</th>
                <th class="p-3">Findings</th>
                <th class="p-3">Remediation Guidance</th>
              </tr>
            </thead>
            <tbody id="table-body" class="divide-y divide-slate-200"></tbody>
          </table>
        </div>
      </div>
    </div>
  </main>

  <script>
    async function runAudit(mock) {
      document.getElementById('loading').classList.remove('hidden');
      document.getElementById('results').classList.add('hidden');
      try {
        const res = await fetch('/api/audit-package', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            gcs_uri: 'gs://asbuilt-sample/job_package.pdf',
            rule_profile: 'all',
            mock_mode: mock
          })
        });
        const data = await res.json();
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('results').classList.remove('hidden');

        document.getElementById('res-status').innerText = data.overall_status;
        document.getElementById('res-status').className = data.overall_status.includes('REJECT') ? 'px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800' : 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800';
        document.getElementById('res-score').innerText = 'Compliance Score: ' + data.compliance_score_pct.toFixed(1) + '%';
        document.getElementById('res-workorder').innerText = 'Job ID: ' + data.job_id + ' | Total Rules: ' + data.total_checks + ' | Defects: ' + data.failed_count;
        document.getElementById('res-download').href = data.scorecard_download_url;

        const tbody = document.getElementById('table-body');
        tbody.innerHTML = '';
        data.report.checks.forEach(c => {
          const row = document.createElement('tr');
          const isFail = c.status === 'FAIL';
          row.className = isFail ? 'bg-red-50/40' : 'hover:bg-slate-50';
          row.innerHTML = `
            <td class="p-3 font-bold">${c.check_id}</td>
            <td class="p-3 font-semibold text-slate-800">${c.check_name}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-xs font-bold ${c.status === 'PASS' ? 'bg-emerald-100 text-emerald-800' : (c.status === 'FAIL' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800')}">${c.status}</span></td>
            <td class="p-3 text-center">${c.pdf_page_index || 'N/A'}</td>
            <td class="p-3 font-mono text-center">${c.drawing_sheet_number || 'N/A'}</td>
            <td class="p-3 text-slate-700">${c.findings}</td>
            <td class="p-3 text-slate-600 italic">${c.remediation_guidance || 'None'}</td>
          `;
          tbody.appendChild(row);
        });
      } catch (err) {
        alert('Audit error: ' + err);
        document.getElementById('loading').classList.add('hidden');
      }
    }

    async function fetchRules() {
      const res = await fetch('/api/rules');
      const data = await res.json();
      alert(`Loaded ${data.rules.length} rules and ${Object.keys(data.profiles).length} profiles from ${data.version}`);
    }
  </script>
</body>
</html>
"""
