###############################################################################
# AWS: cluster ECS Fargate con los dos microservicios y el OpenTelemetry
# Collector como contenedor sidecar dentro de la misma task definition.
#
# En Fargate no hay DaemonSet, asi que el patron equivalente es el sidecar:
# cada tarea lleva su propio Collector y la aplicacion le habla por localhost.
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

data "aws_availability_zones" "disponibles" {
  state = "available"
}

# ------------------------------------------------------------------- red

resource "aws_vpc" "principal" {
  cidr_block           = "10.40.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.nombre}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.principal.id
  tags   = { Name = "${var.nombre}-igw" }
}

resource "aws_subnet" "publica" {
  count                   = 2
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = "10.40.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.disponibles.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.nombre}-publica-${count.index}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.principal.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "publica" {
  count          = 2
  subnet_id      = aws_subnet.publica[count.index].id
  route_table_id = aws_route_table.publica.id
}

resource "aws_security_group" "servicios" {
  name        = "${var.nombre}-sg"
  description = "Trafico de los microservicios y del Collector"
  vpc_id      = aws_vpc.principal.id

  ingress {
    description = "HTTP de la aplicacion"
    from_port   = 8001
    to_port     = 8002
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.principal.cidr_block]
  }

  ingress {
    description = "OTLP gRPC y HTTP"
    from_port   = 4317
    to_port     = 4318
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.principal.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ------------------------------------------------------------------ roles

resource "aws_iam_role" "ejecucion" {
  name = "${var.nombre}-ejecucion"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ejecucion" {
  role       = aws_iam_role.ejecucion.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Rol de la tarea. Es el que usa el Collector para escribir en X-Ray y CloudWatch.
resource "aws_iam_role" "tarea" {
  name = "${var.nombre}-tarea"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "telemetria" {
  name = "${var.nombre}-telemetria"
  role = aws_iam_role.tarea.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameters"]
        Resource = aws_ssm_parameter.config_collector.arn
      },
    ]
  })
}

# ------------------------------------------------------- config del Collector

# La configuracion viaja en Parameter Store, versionada desde el mismo archivo
# YAML del repositorio. No se copia a mano en la consola.
resource "aws_ssm_parameter" "config_collector" {
  name  = "/${var.nombre}/otel-collector-config"
  type  = "String"
  tier  = "Advanced"
  value = file("${path.module}/../../../collector/otel-collector-aws.yaml")
}

resource "aws_cloudwatch_log_group" "aplicacion" {
  name              = "/aws/ecs/${var.nombre}"
  retention_in_days = 14
}

# ------------------------------------------------------------------- ECS

resource "aws_ecs_cluster" "principal" {
  name = "${var.nombre}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_service_discovery_private_dns_namespace" "interno" {
  name = "${var.nombre}.local"
  vpc  = aws_vpc.principal.id
}

resource "aws_service_discovery_service" "service_b" {
  name = "service-b"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.interno.id
    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# --- tarea de service-a, con el Collector como sidecar

resource "aws_ecs_task_definition" "service_a" {
  family                   = "${var.nombre}-service-a"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu_tarea
  memory                   = var.memoria_tarea
  execution_role_arn       = aws_iam_role.ejecucion.arn
  task_role_arn            = aws_iam_role.tarea.arn

  container_definitions = jsonencode([
    {
      name      = "service-a"
      image     = var.imagen_service_a
      essential = true
      portMappings = [{ containerPort = 8001, protocol = "tcp" }]
      environment = [
        { name = "OTEL_ENABLED", value = "true" },
        { name = "OTEL_SERVICE_NAME", value = "service-a" },
        # El sidecar escucha en localhost dentro de la misma tarea.
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://localhost:4317" },
        { name = "SERVICE_B_URL", value = "http://service-b.${var.nombre}.local:8002" },
        { name = "DEPLOYMENT_ENV", value = "production" },
        { name = "CLOUD_PROVIDER", value = "aws" },
        { name = "CLOUD_REGION", value = var.region },
      ]
      dependsOn = [{ containerName = "otel-collector", condition = "START" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.aplicacion.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "service-a"
        }
      }
    },
    {
      name      = "otel-collector"
      image     = var.imagen_collector
      essential = true
      command   = ["--config=env:OTEL_CONFIG"]
      portMappings = [
        { containerPort = 4317, protocol = "tcp" },
        { containerPort = 4318, protocol = "tcp" },
        { containerPort = 8889, protocol = "tcp" },
      ]
      environment = [
        { name = "AWS_REGION", value = var.region },
      ]
      secrets = [
        { name = "OTEL_CONFIG", valueFrom = aws_ssm_parameter.config_collector.arn },
      ]
      healthCheck = {
        command  = ["CMD", "/healthcheck"]
        interval = 30
        timeout  = 5
        retries  = 3
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.aplicacion.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "collector"
        }
      }
    },
  ])
}

resource "aws_ecs_task_definition" "service_b" {
  family                   = "${var.nombre}-service-b"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu_tarea
  memory                   = var.memoria_tarea
  execution_role_arn       = aws_iam_role.ejecucion.arn
  task_role_arn            = aws_iam_role.tarea.arn

  container_definitions = jsonencode([
    {
      name         = "service-b"
      image        = var.imagen_service_b
      essential    = true
      portMappings = [{ containerPort = 8002, protocol = "tcp" }]
      environment = [
        { name = "OTEL_ENABLED", value = "true" },
        { name = "OTEL_SERVICE_NAME", value = "service-b" },
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://localhost:4317" },
        { name = "DEPLOYMENT_ENV", value = "production" },
        { name = "CLOUD_PROVIDER", value = "aws" },
        { name = "CLOUD_REGION", value = var.region },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.aplicacion.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "service-b"
        }
      }
    },
    {
      name         = "otel-collector"
      image        = var.imagen_collector
      essential    = true
      command      = ["--config=env:OTEL_CONFIG"]
      portMappings = [{ containerPort = 4317, protocol = "tcp" }]
      environment  = [{ name = "AWS_REGION", value = var.region }]
      secrets = [
        { name = "OTEL_CONFIG", valueFrom = aws_ssm_parameter.config_collector.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.aplicacion.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "collector-b"
        }
      }
    },
  ])
}

resource "aws_ecs_service" "service_a" {
  name            = "service-a"
  cluster         = aws_ecs_cluster.principal.id
  task_definition = aws_ecs_task_definition.service_a.arn
  desired_count   = var.replicas
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.publica[*].id
    security_groups  = [aws_security_group.servicios.id]
    assign_public_ip = true
  }
}

resource "aws_ecs_service" "service_b" {
  name            = "service-b"
  cluster         = aws_ecs_cluster.principal.id
  task_definition = aws_ecs_task_definition.service_b.arn
  desired_count   = var.replicas
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.publica[*].id
    security_groups  = [aws_security_group.servicios.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.service_b.arn
  }
}
