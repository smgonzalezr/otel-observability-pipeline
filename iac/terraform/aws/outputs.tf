output "cluster_ecs" {
  value = aws_ecs_cluster.principal.name
}

output "vpc_id" {
  value = aws_vpc.principal.id
}

output "log_group" {
  description = "Grupo de CloudWatch donde caen los logs de los dos servicios"
  value       = aws_cloudwatch_log_group.aplicacion.name
}

output "parametro_config_collector" {
  description = "Parametro de SSM con la configuracion del Collector"
  value       = aws_ssm_parameter.config_collector.name
}

output "consola_xray" {
  value = "https://${var.region}.console.aws.amazon.com/xray/home?region=${var.region}#/traces"
}

output "consulta_logs_por_traza" {
  description = "Consulta de CloudWatch Logs Insights para filtrar por trace_id"
  value       = "fields @timestamp, service.name, message, trace_id | filter trace_id = 'PEGAR_TRACE_ID' | sort @timestamp asc"
}
