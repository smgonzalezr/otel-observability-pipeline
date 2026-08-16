variable "project_id" {
  description = "Identificador del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Region donde vive el cluster"
  type        = string
  default     = "us-central1"
}

variable "nombre" {
  description = "Prefijo para los recursos"
  type        = string
  default     = "otel-demo"
}

variable "nodos" {
  description = "Numero de nodos del pool principal"
  type        = number
  default     = 2
}

variable "tipo_maquina" {
  description = "Tipo de maquina de los nodos"
  type        = string
  default     = "e2-standard-2"
}
