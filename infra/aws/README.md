# AWS backend deployment

This Terraform stack runs the existing Docker image as separate ECS Fargate API, worker, and beat tasks behind an HTTPS Application Load Balancer. It creates a private, versioned S3 media bucket and task roles scoped to that bucket. Database, Redis, VPC/subnets, ACM certificate, SMTP, Paystack, and Secrets Manager secrets are supplied from the target AWS account. Private subnets need outbound NAT access for ECR, SMTP, Paystack, and other external providers. Restrict database and Redis inbound security groups to the output `task_security_group_id`.

Required `secret_arns` keys: `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `PAYSTACK_SECRET_KEY`. Store actual values in Secrets Manager, never in Terraform variables or state. `DATABASE_URL` must use TLS and `REDIS_URL` must use `rediss://`. Set exact `api_host`, `frontend_origin`, and the provider-approved `paystack_callback_url`; point the API DNS name to the output ALB name.

1. Build and push the versioned Docker image and set `image_uri` to its immutable digest.
2. Apply with `service_desired_count = 0` to create infrastructure without starting the API.
3. Run the output `release_task_definition` once using `aws ecs run-task` in the private subnets with `task_security_group_id`. Wait for exit code 0; this runs migrations and idempotent bootstrap commands.
4. Apply with `service_desired_count = 1`; check `/health/`, worker and beat logs, `manage.py check --deploy`, and the staging journeys.

The stack is an AWS deployment path, not evidence that an AWS environment has been provisioned. Record account/region, RDS/Redis backup settings, restore drill, DNS, alerting, and provider sandbox results in the release record before promotion.
