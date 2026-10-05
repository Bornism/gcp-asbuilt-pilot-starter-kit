output "service_url" {
  value       = google_cloud_run_v2_service.firewall_service.uri
  description = "Live HTTPS endpoint of the Cloud Run Firewall service"
}

output "storage_bucket" {
  value       = google_storage_bucket.asbuilt_bucket.name
  description = "Name of the ephemeral Cloud Storage staging bucket"
}

output "service_account_email" {
  value       = google_service_account.validator_sa.email
  description = "Email of the least-privilege service account"
}
