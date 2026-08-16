output "cluster_endpoint" {
  description = "Endpoint del cluster GKE"
  value       = google_container_cluster.gke.endpoint
  sensitive   = true
}

output "cluster_nombre" {
  value = google_container_cluster.gke.name
}

output "collector_service_account" {
  description = "Cuenta de servicio que usa el Collector"
  value       = google_service_account.collector.email
}

output "comando_credenciales" {
  description = "Comando para conectar kubectl al cluster"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.gke.name} --region ${var.region} --project ${var.project_id}"
}

output "acceso_jaeger" {
  value = "kubectl -n observability port-forward svc/jaeger-query 16686:16686"
}

output "acceso_grafana" {
  value = "kubectl -n observability port-forward svc/kube-prometheus-stack-grafana 3000:80"
}
