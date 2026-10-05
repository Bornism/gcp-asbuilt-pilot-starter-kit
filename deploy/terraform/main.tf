terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required Services
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Ephemeral Storage Bucket with 24-Hour Purge Lifecycle & CORS
resource "google_storage_bucket" "asbuilt_bucket" {
  name                        = "${var.project_id}-asbuilts"
  location                    = var.region
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 1
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "PUT", "POST", "HEAD", "OPTIONS"]
    response_header = ["Content-Type", "x-goog-resumable"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.services]
}

# 3. Upload Rules Configuration to GCS
resource "google_storage_bucket_object" "rules_config" {
  name   = "config/compliance_rules.yaml"
  bucket = google_storage_bucket.asbuilt_bucket.name
  source = "${path.module}/../../config/compliance_rules.yaml"
}

# 4. Least-Privilege Service Account
resource "google_service_account" "validator_sa" {
  account_id   = "asbuilt-firewall-sa"
  display_name = "Utility As-Built Firewall Service Account"
}

resource "google_project_iam_member" "vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.validator_sa.email}"
}

resource "google_storage_bucket_iam_member" "bucket_admin" {
  bucket = google_storage_bucket.asbuilt_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.validator_sa.email}"
}

# 5. Cloud Run v2 Service
resource "google_cloud_run_v2_service" "firewall_service" {
  name     = "asbuilt-quality-firewall"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.validator_sa.email
    timeout         = "300s"

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.asbuilt_bucket.name
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "RULES_CONFIG_PATH"
        value = "gs://${google_storage_bucket.asbuilt_bucket.name}/config/compliance_rules.yaml"
      }
      env {
        name  = "AUTO_PURGE_SOURCE"
        value = "true"
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.vertex_user,
    google_storage_bucket_iam_member.bucket_admin
  ]
}

# Public invoker for pilot testing
resource "google_cloud_run_service_iam_member" "public_invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloud_run_v2_service.firewall_service.location
  project  = var.project_id
  service  = google_cloud_run_v2_service.firewall_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
