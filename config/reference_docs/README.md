# Reference Job Aides Directory

This directory is intended for static engineering guidelines, utility job aides, standard detail manuals, and specification sheets (PDF format).

## How Context Caching Works in this Starter Kit
When files are placed in this directory (or uploaded to `gs://${GCS_BUCKET_NAME}/config/reference_docs/` in Cloud Storage), the evaluator automatically:
1. Uploads the PDFs to Vertex AI.
2. Creates a **Vertex AI Context Cache** that binds these static reference documents together with the system instructions and rules engine.
3. Caches the reference tokens for 24 hours (configurable).
4. Submits incoming job packages against the cached context, reducing repeated input token costs by up to **75%** and speeding up evaluation latency to ~5–8 seconds.

## Recommended Files to Drop Here:
* `pge_asbuilt_job_aide_rev4.pdf` (or your utility partner's engineering spec handbook)
* `california_pe_stamp_requirements.pdf`
* `standard_electric_framing_details.pdf`
