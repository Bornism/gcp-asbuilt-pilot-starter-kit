# the Contractor & Contractor Field Operations: GCP Pilot Implementation & Onboarding Guide
## Automated As-Built Job Package Quality Firewall via Google Cloud Vertex AI (Gemini Flash)

**Document Version:** 2.0 (Updated Post-October 5 Architectural Alignment)  
**Target Audience:** Adham Abadier (`contractor-tech-lead@contractor.example.com`), Robert "Robby" Mena, Rodolfo Massie, and the Contractor IT/Cloud Engineering  
**Google Cloud Team:** Christopher Duncan (`duncanchris@google.com`), Mandar Vengurlekar, and Steve Munn  

---

## Executive Summary & Pilot Scope

General Utility Infrastructure Contractors completes complex electric and gas distribution projects for Pacific Gas & Electric (PG&E). As part of job completion, the Contractor submits comprehensive **"As-Built" Record Packages**—often 50 to 100+ page PDF sets containing high-resolution CAD schematics, civil alignment profiles, bills of materials (BOM), title blocks, redline markings, and field photos.

When submittal packages contain defects (e.g. missing California Professional Engineer stamps, uninitialed As-Built stamps, or discrepancies between plan conduit footage and billed quantities), PG&E rejects the package as a **"Go-Back"**. Go-Backs cause severe operational friction:
* Crews must be re-dispatched to the field.
* Project billing and invoice payments are delayed 30 to 90+ days.
* Substantial internal rework is incurred by estimators, QA leads, and project managers.

### The Purpose of This Pilot
This pilot deploys a turnkey, automated **Quality Firewall** inside the Contractor’s own Google Cloud project. Operating as a headless, high-speed **"Engine Room"** behind the Contractor's Microsoft 365 environment (SharePoint Online and Power Automate), the firewall audits As-Built packages against utility guidelines (e.g. PG&E Job Aide) and the Contractor’s compliance checklist (17 core checks) in ~8 to 15 seconds, returning an executive, color-coded Excel Scorecard directly to SharePoint before packages are ever sent to PG&E.

---

## 1. End-to-End Architecture & The Middleware Pattern

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 HYBRID UTILITY AS-BUILT PILOT ARCHITECTURE FLOW                                   │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                        │
│  [STEP 1: FIELD DROP]                                                                                  │
│  Field / PM drops 50-100+ page As-Built PDF into SharePoint Online (/Pending_Submittals/)              │
│       │                                                                                                │
│       ▼                                                                                                │
│  [STEP 2: TRIGGER & PRESIGNED URL MINTING]                                                             │
│  Power Automate detects file -> calls Cloud Run: POST /api/generate-presigned-url (~12ms)               │
│  Cloud Run mints 15-minute V4 Signed Upload URL for Google Cloud Storage (GCS)                         │
│       │                                                                                                │
│       ▼                                                                                                │
│  [STEP 3: DIRECT BINARY STREAMING (Zero Azure Memory Exhaustion)]                                      │
│  Power Automate streams PDF straight into GCS via HTTP PUT                                             │
│  * BYPASSES Power Automate 100MB message size limit and 120s timeout                                   │
│       │                                                                                                │
│       ▼                                                                                                │
│  [STEP 4: ASYNCHRONOUS AUDIT EXECUTION]                                                                │
│  Power Automate calls Cloud Run: POST /api/audit-package                                               │
│       │                                                                                                │
│       ├─────────────────────────────────────────┐                                                      │
│       ▼                                         ▼                                                      │
│  Vertex AI: Gemini Flash                  Externalized Rules Engine                                    │
│  • Multimodal Visual & Spatial Audit      • GCS: gs://<bucket>/config/compliance_rules.yaml            │
│  • Context Caching on static Job Aides    • Externalized 17 checks (P.E. stamp, conduit reconciliation)│
│  • Controlled JSON Output Schema          • Non-dev QA configurable via YAML/CSV                      │
│       │                                                                                                │
│       ▼                                                                                                │
│  [STEP 5: IN-MEMORY EXCEL SCORECARD GENERATION]                                                        │
│  Cloud Run generates styled, branded Excel Scorecard (.xlsx) in 250ms via openpyxl                     │
│       │                                                                                                │
│       ├─────────────────────────────────────────┐                                                      │
│       ▼                                         ▼                                                      │
│  [STEP 6: ZERO-RESIDUE PURGE]             [STEP 7: SCORECARD DELIVERY]                                 │
│  Source drawing immediately deleted       Signed GET URL generated -> Power Automate downloads         │
│  via blob.delete() (Lifetime: ~10s)       Deposits Scorecard into SharePoint /Audited_Scorecards/       │
│                                           Posts Adaptive Card summary to Teams / Outlook               │
│                                                                                                        │
│  [NET RESULT: ZERO PERMANENT DRAWING STORAGE IN GOOGLE CLOUD | FULL GO-BACK INTERCEPTION]              │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Why the Middleware Pattern is Mandatory
Attempting to process 50 to 100+ page CAD drawing sets natively inside Microsoft Power Automate or Azure OpenAI creates severe architectural breaking points:
1. **The 100 MB Power Automate Message Limit:** Standard Power Automate HTTP actions cap payloads at 100 MB. Base64 encoding adds a ~33% overhead, meaning a 75 MB blueprint expands to ~100 MB, causing immediate `413 Request Entity Too Large` crashes.
2. **The 120-Second Gateway Timeout:** Power Automate terminates outbound HTTP calls after 120 seconds with `504 GatewayTimeout`. Ingesting 25–50 CAD sheets into traditional multi-hop pipelines frequently exceeds 130 seconds.
3. **The GCS Direct Stream Solution:** Power Automate never holds the file in memory. It requests a V4 Presigned PUT URL, streams the binary stream straight into GCS, and sends only a lightweight JSON pointer (`gs://...`) to Cloud Run.

---

## 2. Pure Gemini Flash Multimodal Inspection (Skipping Document AI OCR)

Based on our October 5 technical review, the Contractor confirmed that the pilot should use **Gemini Flash on Vertex AI natively for all visual and text inspection**, rather than maintaining separate Google Cloud Document AI OCR pipelines.

### Why Pure Gemini Flash Outperforms OCR + Text LLMs
* **CAD Vector Awareness:** Traditional OCR engines (e.g. Azure Document Intelligence) only extract alphanumeric characters into 2D bounding boxes. They cannot understand vector linework, leader arrows, or dashed utility symbols. Gemini Flash natively perceives color channels (red markings vs base CAD layers) and spatial connectivity.
* **The Missing P.E. Stamp Blindspot:** When a Professional Engineer seal box is blank, an OCR engine finds zero text and returns an empty coordinate block. Downstream LLMs never receive a signal that the box exists. Gemini Flash visually inspects the sub-pixel patch inside the circular boundary, detects the absence of seal embossing, and immediately flags **Check #2: FAIL**.
* **Cross-Sheet Arithmetic:** Gemini Flash traces a redline conduit run across Sheet 2 plan views, extracts the field callout `"425 LF of 4-inch PVC"`, scans Sheet 3 BOM tables to find billed quantity `"380 LF"`, computes the 45 LF variance, and flags **Check #8: FAIL**.
* **90%+ Cost Reduction:** Document AI costs ~$0.05/page ($5.00 for a 100-page package). Gemini Flash processes native visual tokens for less than **$0.01 to $0.03 total per 100-page package**.

### Token & Cost Optimization Techniques

#### 1. Vertex AI Context Caching
Utility design guidelines (such as PG&E's 80-page As-Built Job Aide) rarely change between submittals. In this starter kit:
* Reference PDFs in `config/reference_docs/` are pre-cached in Vertex AI with a 24-hour TTL.
* When auditing incoming packages, Gemini Flash reuses the cached prefix tokens.
* **Result:** Input token costs for the reference specifications are reduced by **up to 75%**, and initial token time-to-first-byte latency drops by over 60%.

#### 2. Fine-Grained `media_resolution` Controls
Standard text sheets do not require ultra-high image resolution, while dense 24" × 36" (Arch D) CAD layout drawings require high detail for wire gauge callouts:
* Administrative sheets (Sheet Index, Foremen logs) are processed with standard resolution.
* CAD alignment sheets and P.E. stamp boxes are processed with `MEDIA_RESOLUTION_HIGH` to ensure sub-pixel clarity on leader lines and stamp text.

#### 3. Controlled Generation (`response_schema`)
To eliminate AI hallucinations, the service mathematically binds Gemini Flash to the strict `JobPackageAuditReport` Pydantic schema using Vertex AI's `response_mime_type="application/json"`:
* Forces exact enumeration of statuses: `PASS`, `FAIL`, `N/A`, `NEEDS_REVIEW`.
* Guarantees structured findings and remediation steps.

#### 4. Dual Page Indexing: Eliminating Page-Number Drift
In utility packages, PDF cover sheets, change orders, or slip-sheets frequently shift physical page numbers relative to printed drawings:
* Gemini returns **both** the physical 1-based index (`pdf_page_index`: `3`) **and** the printed title block drawing identifier (`drawing_sheet_number`: `Sheet 2 of 4` or `D-102`).
* Field technicians can locate the exact CAD print instantly, regardless of how the PDF was merged.

---

## 3. Configurable Rules & Policy Engine (For QA Leads & Non-Developers)

Compliance specifications evolve when PG&E updates utility bulletins or when the Contractor expands to other utilities (e.g. Southern California Edison, SDG&E). 

To ensure the Contractor is not dependent on software engineers to update compliance checks, the starter kit **externalizes all evaluation rules into a clean configuration file stored in Google Cloud Storage**:
`gs://<PROJECT_ID>-asbuilts/config/compliance_rules.yaml`

### How a QA Lead or Project Manager Adds or Edits Rules

#### Option A: Editing `compliance_rules.yaml` (Recommended)
A QA Lead can download the YAML file, edit it in any text editor, and upload it back to GCS. The engine supports hot-reloading via `POST /api/rules/reload`:

```yaml
rules:
  - id: 18
    name: "Wildfire Hardening Mesh Wrap"
    category: "Safety"
    severity: "CRITICAL"
    evaluation_criteria: >
      In High Fire Threat Districts (HFTD Tier 2 or 3), verify that all new wood poles
      specify non-combustible protective mesh wrap extending 10 feet up from ground line.
    remediation_template: >
      Add wildfire protective mesh wrap note and specify mesh manufacturer callout on Sheet 2.
```

#### Option B: Managing Rules via Spreadsheet / CSV
For non-technical team members who prefer working in Excel:
1. Open `config/compliance_rules_template.csv` in Excel.
2. Edit rule descriptions, categories, or severity ratings.
3. Save as CSV and upload to `gs://<BUCKET>/config/compliance_rules_template.csv`.

### Workload Rule Profiles
Utility construction packages have different scopes. The engine includes 5 built-in profiles that can be selected in Power Automate without altering rule definitions:

| Profile Key | Target Scope | Active Checks Evaluated |
| :--- | :--- | :--- |
| **`all`** | Full Turnkey Construction | All 17 checks (Administrative, Spatial, Material, Safety) |
| **`electric_underground`** | Subsurface Conduit & Vaults | Checks 1, 2, 3, 4, 5, 7, 8, 10, 11, 13, 14, 17 |
| **`overhead_electric`** | Poles, Crossarms, Reconductoring | Checks 1, 2, 3, 4, 5, 6, 9, 11, 12, 13, 14, 16, 17 |
| **`civil_trenching`** | Trenching, Potholing, Paving | Checks 1, 3, 5, 6, 7, 8, 10, 13, 15 |
| **`financial_reconciliation`**| Accounting & Work Order True-up | Checks 1, 4, 8, 11, 14 (Conduit footage vs BOM tallies) |

---

## 4. Step-by-Step Google Cloud Onboarding & Provisioning

### Prerequisites
1. **Google Cloud Project:** A dedicated project ID (e.g. `utility-asbuilt-pilot`).
2. **Billing Account:** Linked active billing account.
3. **User Access:** Adham Abadier has `roles/owner` or `roles/editor` + `roles/resourcemanager.projectIamAdmin`.
4. **Environment:** Google Cloud Shell (recommended—zero local installation required).

### Option 1: 1-Click Automated Setup (`deploy/setup_pilot.sh`)
From Google Cloud Shell inside your GCP project:
```bash
# 1. Clone the starter kit repository
git clone https://github.com/Bornism/gcp-asbuilt-pilot-starter-kit.git
cd gcp-asbuilt-pilot-starter-kit

# 2. Execute automated provisioning (Takes ~3 minutes)
chmod +x deploy/setup_pilot.sh
./deploy/setup_pilot.sh
```
The script automatically enables required APIs, provisions the ephemeral GCS bucket with CORS and 24-hour auto-purge lifecycles, configures the service account, uploads rule configs, and deploys the Cloud Run service.

### Option 2: Infrastructure-as-Code via Terraform (`deploy/terraform/`)
For teams managing infrastructure via HashiCorp Terraform:
```bash
cd deploy/terraform
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID" -var="region=us-central1"
```

---

## 5. Microsoft Power Automate Integration Guide (Click-by-Click)

Inside the Contractor’s Microsoft 365 environment, configure an **Automated Cloud Flow**:

```
[SharePoint Trigger: When a file is created or modified]
       │
       ▼
[Action 1: HTTP POST - Request Presigned URL from Cloud Run]
       │
       ▼
[Action 2: HTTP PUT - Stream PDF directly into Cloud Storage]
       │
       ▼
[Action 3: HTTP POST - Trigger Gemini Flash Audit]
       │
       ▼
[Action 4: HTTP GET - Download Excel Scorecard]
       │
       ▼
[Action 5: SharePoint - Save File in /Audited_Scorecards/]
       │
       ▼
[Action 6: Teams - Post Adaptive Card Summary]
```

### Action 1: Request Presigned Upload URL
* **Connector:** `HTTP`
* **Method:** `POST`
* **URI:** `https://<YOUR-CLOUD-RUN-URL>/api/generate-presigned-url`
* **Headers:** `{"Content-Type": "application/json"}`
* **Body:**
  ```json
  {
    "filename": "@{triggerOutputs()?['body/{FilenameWithExtension}']}"
  }
  ```

### Action 2: Direct Binary Stream to GCS
* **Connector:** `HTTP`
* **Method:** `PUT`
* **URI:** `@{body('Action_1')?['upload_url']}`
* **Headers:** `{"Content-Type": "application/pdf"}`
* **Body:** `@{body('Get_file_content_from_SharePoint')}`

### Action 3: Trigger Audit & Scorecard Generation
* **Connector:** `HTTP`
* **Method:** `POST`
* **URI:** `https://<YOUR-CLOUD-RUN-URL>/api/audit-package`
* **Headers:** `{"Content-Type": "application/json"}`
* **Body:**
  ```json
  {
    "gcs_uri": "@{body('Action_1')?['gcs_uri']}",
    "filename": "@{triggerOutputs()?['body/{FilenameWithExtension}']}",
    "rule_profile": "all",
    "auto_purge_source": true
  }
  ```

### Action 4: Download Scorecard & Deposit in SharePoint
* **Connector:** `HTTP` (Method: `GET`, URI: `@{body('Action_3')?['scorecard_download_url']}`)
* **Next Action:** SharePoint `Create File`:
  * **Folder:** `/Shared Documents/Audited_Scorecards`
  * **File Name:** `@{body('Action_3')?['scorecard_filename']}`
  * **File Content:** `@{body('Action_4')}`

---

## 6. Pilot vs. Production Readiness Assessment

This starter kit is optimized for a fast, friction-free **Proof of Concept / Pilot demonstration**. While the core evaluation pipeline and openpyxl scorecard generator are enterprise-grade, moving from this pilot to full enterprise production scale requires implementing the following architectural controls:

| Architecture Domain | Pilot / POC Implementation (Included Today) | Enterprise Production Implementation (Next Phase) |
| :--- | :--- | :--- |
| **Authentication & Identity** | HTTPS endpoints using IAM service account or API tokens; optional `--allow-unauthenticated` for testing. | **Workload Identity Federation (WIF):** Passwordless authentication between Azure AD / Entra ID and Google Cloud IAM. Zero static keys. |
| **Network & Data Boundary** | Public Cloud Run HTTPS URL with CORS; TLS 1.3 encryption in transit. | **VPC Service Controls (VPC-SC) & Private Service Connect (PSC):** Encloses GCS, Vertex AI, and Cloud Run in an isolated cryptographic perimeter. |
| **Asynchronous Orchestration** | Synchronous HTTP call from Power Automate to Cloud Run (under 15s execution). | **Eventarc + Cloud Pub/Sub + Cloud Tasks:** Decoupled event queue with automatic retries, exponential backoff, and Dead-Letter Queues (DLQ). |
| **Quota & Throughput** | Standard Vertex AI on-demand quota (~60 requests/minute). | **Provisioned Throughput & Dynamic Shared Quota (DSQ):** Dedicated GPU/TPU reservation for guaranteed SLAs during peak 4 PM field drop rushes. |
| **Human-in-the-Loop (HITL)** | Direct Excel scorecard output to SharePoint for human review. | **Automated Routing & Confidence Thresholds:** Scores $\ge 95\%$ auto-routed to PG&E submittal API; borderline scores routed to QA leads. |
| **Data Governance & Zero-Residue** | Ephemeral Cloud Storage with immediate `blob.delete()` and 24-hr TTL bucket policy. | **Customer-Managed Encryption Keys (CMEK):** Keys stored in the Contractor's Cloud KMS; BigQuery audit table logging audit metadata (zero drawing retention). |

---

## 7. Security, CEII Compliance, & Enterprise Data Governance

1. **Zero Model Training Guarantee:** Under Google Cloud’s commercial terms, customer data, CAD blueprints, prompt instructions, and generated scorecards are **never used to train Google foundation models**.
2. **US Sovereign Data Residency:** All inference (Vertex AI Gemini Flash), compute (Cloud Run), and ephemeral storage (GCS) are restricted strictly to US regions (`us-central1`).
3. **Critical Energy Infrastructure Information (CEII) Protection:** Because drawings are purged immediately post-audit (`blob.delete()`), the Contractor maintains complete custody of critical utility grid schematics within Microsoft 365.

---

## 8. Support & Contact Information
* **Christopher Duncan**, Customer Engineer (`duncanchris@google.com`)
* **Mandar Vengurlekar**, Customer Engineer
* **Steve Munn**, Account Executive
