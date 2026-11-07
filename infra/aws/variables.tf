variable "region" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "certificate_arn" { type = string }
variable "image_uri" { type = string }
variable "api_host" { type = string }
variable "frontend_origin" { type = string }
variable "email_host" { type = string }
variable "paystack_callback_url" { type = string }
variable "media_bucket_name" { type = string }
variable "secret_arns" {
  type = map(string)
  validation {
    condition = alltrue([for name in [
      "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "SUPER_ADMIN_EMAIL",
      "SUPER_ADMIN_PASSWORD", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD",
      "PAYSTACK_SECRET_KEY"
    ] : contains(keys(var.secret_arns), name)])
    error_message = "Missing a required backend secret ARN."
  }
}
variable "service_desired_count" {
  type    = number
  default = 0
  validation {
    condition     = contains([0, 1], var.service_desired_count)
    error_message = "Use 0 for initial provisioning or 1 after the release task succeeds."
  }
}
