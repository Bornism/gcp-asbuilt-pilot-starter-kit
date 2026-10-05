"""
Externalized Rules & Policy Loader
==================================
Loads compliance rules and workload profiles from:
1. Google Cloud Storage (e.g. gs://bucket/config/compliance_rules.yaml)
2. Local filesystem YAML, JSON, or CSV files

Allows non-technical QA leads or project managers to update evaluation
criteria without modifying application code or redeploying containers.
"""

import os
import csv
import json
import logging
from typing import Dict, List, Optional, Any
import yaml
from google.cloud import storage

logger = logging.getLogger("rules-loader")


class RulesEngine:
    def __init__(self, config_path: Optional[str] = None, storage_client: Optional[storage.Client] = None):
        self.config_path = config_path or os.getenv("RULES_CONFIG_PATH", "config/compliance_rules.yaml")
        self.storage_client = storage_client
        self.rules: List[Dict[str, Any]] = []
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.version: str = "1.0"
        self.last_updated: str = ""
        self.load_rules()

    def load_rules(self) -> None:
        """Reads rules from either GCS or the local file system."""
        try:
            content = self._fetch_content(self.config_path)
            if self.config_path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(content)
                self.rules = data.get("rules", [])
                self.profiles = data.get("profiles", {})
                self.version = data.get("version", "1.0")
                self.last_updated = data.get("last_updated", "")
            elif self.config_path.endswith(".json"):
                data = json.loads(content)
                self.rules = data.get("rules", [])
                self.profiles = data.get("profiles", {})
            elif self.config_path.endswith(".csv"):
                self._load_from_csv(content)
            else:
                raise ValueError(f"Unsupported configuration format: {self.config_path}")

            logger.info(f"Loaded {len(self.rules)} rules and {len(self.profiles)} profiles from {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading rules from {self.config_path}: {e}. Falling back to default built-ins.")
            self._load_fallback_rules()

    def _fetch_content(self, path: str) -> str:
        """Helper to fetch content whether located in GCS or locally."""
        if path.startswith("gs://"):
            if not self.storage_client:
                self.storage_client = storage.Client()
            parts = path.replace("gs://", "").split("/", 1)
            bucket_name, blob_name = parts[0], parts[1]
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.download_as_text()
        else:
            # Local filesystem
            resolved_path = os.path.abspath(path)
            if not os.path.exists(resolved_path):
                # Try relative to repo root
                alt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)
                if os.path.exists(alt_path):
                    resolved_path = alt_path
            with open(resolved_path, "r", encoding="utf-8") as f:
                return f.read()

    def _load_from_csv(self, csv_text: str) -> None:
        """Parses a CSV rules file."""
        reader = csv.DictReader(csv_text.splitlines())
        self.rules = []
        for row in reader:
            self.rules.append({
                "id": int(row.get("Rule ID", len(self.rules) + 1)),
                "name": row.get("Rule Name", "").strip(),
                "category": row.get("Category", "Administrative").strip(),
                "severity": row.get("Severity", "MAJOR").strip(),
                "evaluation_criteria": row.get("Evaluation Criteria", "").strip(),
                "remediation_template": row.get("Remediation Guidance", "").strip(),
            })
        self.profiles = {"all": {"description": "All CSV Rules", "rule_ids": [r["id"] for r in self.rules]}}

    def _load_fallback_rules(self) -> None:
        """Provides default 17 rules if external loading fails."""
        self.rules = [
            {"id": 1, "name": "Title Block Completeness", "category": "Administrative", "severity": "CRITICAL", "evaluation_criteria": "Verify WO #, Job #, City, Designer, and Date are present.", "remediation_template": "Populate all missing title block fields before submittal."},
            {"id": 2, "name": "Mandatory Signatures & PE Stamp", "category": "Administrative", "severity": "CRITICAL", "evaluation_criteria": "Verify California P.E. digital seal/signature is present where required. Blank box is an automatic fail.", "remediation_template": "Submit package to licensed P.E. for digital wet-stamp and seal."},
            {"id": 3, "name": "As-Built Stamp & Dating", "category": "Administrative", "severity": "CRITICAL", "evaluation_criteria": "Confirm official RECORD DRAWING / AS-BUILT stamp is affixed with Foreman signature and date.", "remediation_template": "Apply official red As-Built stamp, obtain field signature, and record completion date."},
            {"id": 4, "name": "Sheet Index & Versioning", "category": "Administrative", "severity": "MAJOR", "evaluation_criteria": "Verify all sheets listed in cover index exist with matching revision numbers.", "remediation_template": "Reconcile package sheets against cover index; re-insert missing sheets."},
            {"id": 5, "name": "Redline Legibility & Standard", "category": "Spatial/Visual", "severity": "MAJOR", "evaluation_criteria": "Verify all field changes are drawn in clean red markings with legible callouts.", "remediation_template": "Redraw field revisions in clean red markings and re-scan at 300+ DPI."},
            {"id": 6, "name": "North Arrow & Orientation", "category": "Spatial/Visual", "severity": "MINOR", "evaluation_criteria": "Confirm plan view drawings display a clear North arrow and graphic scale bar.", "remediation_template": "Add standard North arrow indicator and graphic bar scale to upper right quadrant."},
            {"id": 7, "name": "Trench Depth & Cover Compliance", "category": "Safety", "severity": "CRITICAL", "evaluation_criteria": "Verify minimum trench cover complies with CPUC GO 128 (min 36 in secondary, 42 in primary).", "remediation_template": "Document measured trench depth on profile sheets or attach approved variance."},
            {"id": 8, "name": "Conduit Footage vs. BOM Reconciliation", "category": "Material/BOM", "severity": "CRITICAL", "evaluation_criteria": "Compare sum of plan conduit footage against billed linear footage in BOM tally sheet (max variance ±2%).", "remediation_template": "Reconcile plan conduit footage with final BOM tally sheet before submittal."},
            {"id": 9, "name": "Conductor Framing & Pole Details", "category": "Spatial/Visual", "severity": "MAJOR", "evaluation_criteria": "Check pole height, class, and framing assemblies against utility engineering standards.", "remediation_template": "Update pole detail callouts to reflect true as-constructed framing configuration."},
            {"id": 10, "name": "Subsurface Utility Markings (USA 811)", "category": "Safety", "severity": "CRITICAL", "evaluation_criteria": "Verify active USA 811 locate ticket number and expiration date are recorded.", "remediation_template": "Record valid USA 811 ticket number, date, and locate clearance notes on general note sheet."},
            {"id": 11, "name": "Transformer & Equipment Specifications", "category": "Material/BOM", "severity": "MAJOR", "evaluation_criteria": "Verify major equipment kVA rating, serial numbers, and mounting match approved design.", "remediation_template": "Update equipment schedules with exact nameplate kVA rating and manufacturer serial #."},
            {"id": 12, "name": "Joint-Use Clearances (CPUC GO 95)", "category": "Safety", "severity": "CRITICAL", "evaluation_criteria": "Verify vertical clearance between power conductors and telecom meets CPUC GO 95 (min 40 inches).", "remediation_template": "Verify field attachment heights on elevation detail sheet and confirm 40 in separation."},
            {"id": 13, "name": "GPS & GIS Tie-in Coordinates", "category": "Spatial/Visual", "severity": "MAJOR", "evaluation_criteria": "Confirm newly set poles, vaults, and tie-in points include GPS coordinates or surveyor benchmarks.", "remediation_template": "Add GIS survey coordinates or reference stationing offsets for newly installed facilities."},
            {"id": 14, "name": "Material Reconciliation & Scrap Tally", "category": "Material/BOM", "severity": "MAJOR", "evaluation_criteria": "Verify hardware items shown on print correspond with material return/reconciliation sheet.", "remediation_template": "True-up installed hardware counts against warehouse requisitions and log unused material."},
            {"id": 15, "name": "Environmental & Permitting Compliance", "category": "Administrative", "severity": "MAJOR", "evaluation_criteria": "Verify environmental protection conditions and municipal encroachment permit numbers are noted.", "remediation_template": "Include municipal permit number and certified compliance statement for environmental conditions."},
            {"id": 16, "name": "Field Photo Alignment", "category": "Spatial/Visual", "severity": "MAJOR", "evaluation_criteria": "Verify included field photos cross-reference specific drawing sheets, pole numbers, or stationing.", "remediation_template": "Annotate each field photo with date taken, view orientation, and asset ID."},
            {"id": 17, "name": "Scope & Circuit Boundary Closure", "category": "Safety", "severity": "CRITICAL", "evaluation_criteria": "Confirm newly installed circuit work clearly designates source facility without ambiguous gaps.", "remediation_template": "Clearly label circuit tie-in boundary, existing device identifier, and phase orientation."}
        ]
        self.profiles = {"all": {"description": "Default All 17 Rules", "rule_ids": list(range(1, 18))}}

    def get_active_rules(self, profile: Optional[str] = "all", selected_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Returns the list of active rule dicts based on chosen profile or specific IDs."""
        if selected_ids:
            target_ids = set(selected_ids)
            return [r for r in self.rules if r["id"] in target_ids]
        
        if profile and profile in self.profiles:
            target_ids = set(self.profiles[profile].get("rule_ids", []))
            return [r for r in self.rules if r["id"] in target_ids]

        return self.rules

    def compile_prompt_instructions(self, profile: Optional[str] = "all", selected_ids: Optional[List[int]] = None) -> str:
        """Formats the active rules into a clear prompt block for Gemini Flash."""
        active = self.get_active_rules(profile=profile, selected_ids=selected_ids)
        lines = []
        for r in active:
            lines.append(
                f"- Rule #{r['id']} [{r['category']} - Severity: {r.get('severity', 'MAJOR')}]: {r['name']}\n"
                f"  Evaluation Criteria: {r['evaluation_criteria']}\n"
                f"  Default Remediation: {r.get('remediation_template', 'N/A')}"
            )
        return "\n".join(lines)
