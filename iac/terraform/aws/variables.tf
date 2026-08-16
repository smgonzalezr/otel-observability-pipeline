variable "region" {
  description = "Region de AWS"
  type        = string
  default     = "us-east-1"
}

variable "nombre" {
  description = "Prefijo para los recursos"
  type        = string
  default     = "otel-demo"
}

variable "replicas" {
  description = "Tareas por servicio"
  type        = number
  default     = 2
}

variable "cpu_tarea" {
  description = "Unidades de CPU por tarea (1024 = 1 vCPU)"
  type        = string
  default     = "1024"
}

variable "memoria_tarea" {
  description = "Memoria por tarea en MiB"
  type        = string
  default     = "2048"
}

variable "imagen_service_a" {
  description = "Imagen de service-a en ECR"
  type        = string
}

variable "imagen_service_b" {
  description = "Imagen de service-b en ECR"
  type        = string
}

variable "imagen_collector" {
  description = "Imagen del OpenTelemetry Collector"
  type        = string
  default     = "otel/opentelemetry-collector-contrib:0.113.0"
}
