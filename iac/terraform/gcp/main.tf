###############################################################################
# GCP: cluster GKE, los dos microservicios y el OpenTelemetry Collector.
#
# El Collector va como DaemonSet para que cada nodo tenga su propio punto de
# recepcion. La aplicacion nunca habla con un backend, siempre con el Collector.
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    google     = { source = "hashicorp/google", version = "~> 5.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --------------------------------------------------------------- red y cluster

resource "google_compute_network" "vpc" {
  name                    = "${var.nombre}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subred" {
  name          = "${var.nombre}-subred"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = "10.10.0.0/20"

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.20.0.0/16"
  }
  secondary_ip_range {
    range_name    = "servicios"
    ip_cidr_range = "10.30.0.0/20"
  }
}

resource "google_container_cluster" "gke" {
  name     = "${var.nombre}-gke"
  location = var.region

  network    = google_compute_network.vpc.id
  subnetwork = google_compute_subnetwork.subred.id

  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "servicios"
  }

  # Workload Identity evita guardar llaves de servicio en el cluster.
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"
}

resource "google_container_node_pool" "principal" {
  name       = "principal"
  cluster    = google_container_cluster.gke.id
  location   = var.region
  node_count = var.nodos

  node_config {
    machine_type = var.tipo_maquina
    disk_size_gb = 50
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      componente = "observabilidad-demo"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ------------------------------------------- identidad para el Collector

resource "google_service_account" "collector" {
  account_id   = "${var.nombre}-collector"
  display_name = "OpenTelemetry Collector"
}

# Permisos minimos: escribir trazas, metricas y logs. Nada mas.
resource "google_project_iam_member" "collector_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.collector.email}"
}

resource "google_project_iam_member" "collector_metrics" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.collector.email}"
}

resource "google_project_iam_member" "collector_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.collector.email}"
}

# Enlaza la cuenta de GCP con la cuenta de Kubernetes.
resource "google_service_account_iam_member" "workload_identity" {
  service_account_id = google_service_account.collector.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[observability/otel-collector]"
}

# --------------------------------------------------------------- kubernetes

provider "kubernetes" {
  host                   = "https://${google_container_cluster.gke.endpoint}"
  token                  = data.google_client_config.actual.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${google_container_cluster.gke.endpoint}"
    token                  = data.google_client_config.actual.access_token
    cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
  }
}

data "google_client_config" "actual" {}

resource "kubernetes_namespace" "observabilidad" {
  metadata { name = "observability" }
}

resource "kubernetes_namespace" "aplicacion" {
  metadata { name = "demo" }
}

resource "kubernetes_service_account" "collector" {
  metadata {
    name      = "otel-collector"
    namespace = kubernetes_namespace.observabilidad.metadata[0].name
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.collector.email
    }
  }
}

# La configuracion del Collector vive en un ConfigMap versionado en el repo.
resource "kubernetes_config_map" "collector" {
  metadata {
    name      = "otel-collector-config"
    namespace = kubernetes_namespace.observabilidad.metadata[0].name
  }
  data = {
    "config.yaml" = file("${path.module}/../../../collector/otel-collector-gcp.yaml")
  }
}

# --------------------------------------------------------------- backends

resource "helm_release" "jaeger" {
  name       = "jaeger"
  repository = "https://jaegertracing.github.io/helm-charts"
  chart      = "jaeger"
  namespace  = kubernetes_namespace.observabilidad.metadata[0].name

  set {
    name  = "allInOne.enabled"
    value = "true"
  }
  set {
    name  = "collector.service.otlp.grpc.port"
    value = "4317"
  }
  set {
    name  = "storage.type"
    value = "memory"
  }
}

resource "helm_release" "prometheus_grafana" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.observabilidad.metadata[0].name

  values = [file("${path.module}/valores-grafana.yaml")]
}
