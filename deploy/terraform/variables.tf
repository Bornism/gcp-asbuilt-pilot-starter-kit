variable "project_id" {
  type        = string
  description = "Google Cloud Project ID where the pilot will be deployed"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud region for Cloud Run, Vertex AI, and Storage"
}

variable "gemini_model" {
  type        = string
  default     = "gemini-2.5-flash"
  description = "Vertex AI Gemini foundation model"
}

variable "container_image" {
  type        = string
  default     = "gcr.io/cloudrun/hello" # Placeholder: override with built Artifact Registry image
  description = "Container image URL to deploy to Cloud Run"
}

variable "allow_unauthenticated" {
  type        = bool
  default     = true
  description = "Whether to allow unauthenticated invocations for initial pilot testing"
}
