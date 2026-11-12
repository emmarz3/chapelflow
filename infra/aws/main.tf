terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.region }

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/chapelflow/${var.environment}/backend"
  retention_in_days = 30
}

resource "aws_s3_bucket" "private_media" {
  bucket = var.media_bucket_name
}

resource "aws_s3_bucket_public_access_block" "private_media" {
  bucket                  = aws_s3_bucket.private_media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "private_media" {
  bucket = aws_s3_bucket.private_media.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private_media" {
  bucket = aws_s3_bucket.private_media.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_iam_role" "execution" {
  name = "chapelflow-${var.environment}-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "read_secrets" {
  name = "chapelflow-${var.environment}-read-secrets"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = values(var.secret_arns)
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "chapelflow-${var.environment}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "private_media" {
  name = "chapelflow-${var.environment}-private-media"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource = "${aws_s3_bucket.private_media.arn}/*"
    }]
  })
}

resource "aws_security_group" "api" {
  name   = "chapelflow-${var.environment}-api"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 10000
    to_port         = 10000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "alb" {
  name   = "chapelflow-${var.environment}-alb"
  vpc_id = var.vpc_id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 10000
    to_port     = 10000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "api" {
  name               = "chapelflow-${var.environment}-api"
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "api" {
  name        = "chapelflow-${var.environment}-api"
  port        = 10000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check { path = "/health/" }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_cluster" "backend" {
  name = "chapelflow-${var.environment}"
}

locals {
  common_environment = [
    { name = "DJANGO_SETTINGS_MODULE", value = "config.settings.production" },
    { name = "PORT", value = "10000" },
    { name = "ALLOWED_HOSTS", value = var.api_host },
    { name = "PUBLIC_BACKEND_URL", value = "https://${var.api_host}" },
    { name = "CORS_ALLOWED_ORIGINS", value = var.frontend_origin },
    { name = "CSRF_TRUSTED_ORIGINS", value = var.frontend_origin },
    { name = "STORAGE_PROVIDER", value = "s3" },
    { name = "AWS_USE_IAM_ROLE", value = "true" },
    { name = "AWS_STORAGE_BUCKET_NAME", value = aws_s3_bucket.private_media.bucket },
    { name = "AWS_S3_REGION_NAME", value = var.region },
    { name = "EMAIL_HOST", value = var.email_host },
    { name = "PAYSTACK_CALLBACK_URL", value = var.paystack_callback_url },
  ]
  common_secrets = [for name, arn in var.secret_arns : { name = name, valueFrom = arn }]
  commands = {
    api     = ["/app/start.sh"]
    worker  = ["/app/start-celery.sh", "worker"]
    beat    = ["/app/start-celery.sh", "beat"]
    release = ["/app/release.sh"]
  }
}

resource "aws_ecs_task_definition" "backend" {
  for_each                 = local.commands
  family                   = "chapelflow-${var.environment}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name         = "backend"
    image        = var.image_uri
    essential    = true
    command      = each.value
    environment  = local.common_environment
    secrets      = local.common_secrets
    portMappings = each.key == "api" ? [{ containerPort = 10000, protocol = "tcp" }] : []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend.name
        awslogs-region        = var.region
        awslogs-stream-prefix = each.key
      }
    }
  }])
}

resource "aws_ecs_service" "backend" {
  for_each        = toset(["api", "worker", "beat"])
  name            = "chapelflow-${var.environment}-${each.key}"
  cluster         = aws_ecs_cluster.backend.id
  task_definition = aws_ecs_task_definition.backend[each.key].arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }
  dynamic "load_balancer" {
    for_each = each.key == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.api.arn
      container_name   = "backend"
      container_port   = 10000
    }
  }
  depends_on = [aws_lb_listener.https]
}

output "cluster_name" { value = aws_ecs_cluster.backend.name }
output "release_task_definition" { value = aws_ecs_task_definition.backend["release"].arn }
output "alb_dns_name" { value = aws_lb.api.dns_name }
output "task_security_group_id" { value = aws_security_group.api.id }
