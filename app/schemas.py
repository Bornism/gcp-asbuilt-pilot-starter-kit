"""
Pydantic Schemas for Controlled Generation & API Payloads
=========================================================
Enforces deterministic JSON output from Gemini Flash with:
- Strict Status typing: PASS, FAIL, NOT_APPLICABLE, NEEDS_REVIEW
- Dual page indexing: 1-based PDF index AND printed drawing sheet number
- Field deficiency analysis and actionable remediation guidance
"""

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "N/A"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class CheckCategory(str, Enum):
    ADMINISTRATIVE = "Administrative"
    SPATIAL_VISUAL = "Spatial/Visual"
    MATERIAL_BOM = "Material/BOM"
    SAFETY = "Safety"


class RuleSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class ComplianceCheckResult(BaseModel):
    check_id: int = Field(
        description="The integer ID of the compliance check matching the rules engine."
    )
    check_name: str = Field(
        description="The official title/name of the compliance check."
    )
    category: str = Field(
        description="Administrative, Spatial/Visual, Material/BOM, or Safety."
    )
    severity: str = Field(
        default="MAJOR",
        description="CRITICAL, MAJOR, or MINOR severity rating."
    )
    status: CheckStatus = Field(
        description="Result of the check: PASS, FAIL, N/A, or NEEDS_REVIEW."
    )
    pdf_page_index: Optional[int] = Field(
        default=None,
        description="The 1-based physical PDF page index where the finding or defect was detected."
    )
    drawing_sheet_number: Optional[str] = Field(
        default=None,
        description="The printed engineering sheet number from the title block (e.g. 'Sheet 2 of 5', 'D-02', 'C-101') to avoid page-drift."
    )
    findings: str = Field(
        description="Detailed observation explaining the compliance finding, verified dimensions, or defect details."
    )
    remediation_guidance: Optional[str] = Field(
        default=None,
        description="Clear, actionable steps for the field technician or project manager to correct the defect prior to customer submittal."
    )


class JobPackageAuditReport(BaseModel):
    job_package_id: str = Field(
        description="The internal contractor Job or Work Order identifier."
    )
    utility_work_order: str = Field(
        description="The utility client work order number (e.g. 'WO-440219-FRESNO')."
    )
    overall_compliance_status: str = Field(
        description="'PASS - READY FOR SUBMITTAL', 'REJECTED - GO-BACK DETECTED', or 'NEEDS REVIEW'"
    )
    total_checks: int = Field(default=0)
    passed_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    review_count: int = Field(default=0)
    na_count: int = Field(default=0)
    compliance_score_pct: float = Field(
        default=0.0,
        description="Percentage of applicable checks passed (0.0 to 100.0)."
    )
    checks: List[ComplianceCheckResult] = Field(
        description="List of individual evaluation results for each evaluated rule."
    )


# --- API Request & Response Schemas ---

class PresignedUrlRequest(BaseModel):
    filename: str = Field(description="Name of the PDF file to upload (e.g., job_package.pdf).")
    content_type: Optional[str] = Field(default="application/pdf")


class PresignedUrlResponse(BaseModel):
    upload_url: str = Field(description="V4 Presigned PUT URL valid for 15 minutes.")
    gcs_uri: str = Field(description="Internal GCS destination URI (gs://bucket/uploads/...).")
    blob_name: str = Field(description="Storage object path in bucket.")


class AuditRequest(BaseModel):
    gcs_uri: str = Field(
        description="Google Cloud Storage URI of the uploaded job package PDF (gs://...)."
    )
    filename: Optional[str] = Field(
        default="job_package.pdf",
        description="Human-readable filename for scorecard naming."
    )
    rule_profile: Optional[str] = Field(
        default="all",
        description="Rule profile key: 'all', 'electric_underground', 'overhead_electric', 'civil_trenching', 'financial_reconciliation'."
    )
    selected_rule_ids: Optional[List[int]] = Field(
        default=None,
        description="Optional list of specific rule IDs to evaluate, overriding the profile."
    )
    auto_purge_source: Optional[bool] = Field(
        default=True,
        description="Zero-Residue: Immediately delete the source PDF from GCS post-audit."
    )
    mock_mode: Optional[bool] = Field(
        default=False,
        description="If True, returns a deterministic synthetic audit report without invoking Vertex AI."
    )


class AuditResponse(BaseModel):
    job_id: str
    overall_status: str
    compliance_score_pct: float
    total_checks: int
    failed_count: int
    scorecard_filename: str
    scorecard_download_url: str
    gcs_scorecard_uri: str
    source_purged: bool
    report: JobPackageAuditReport
