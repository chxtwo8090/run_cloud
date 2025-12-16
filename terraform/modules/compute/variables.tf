variable "project_name" { type = string }

variable "public_subnet_id" {
  description = "Bastion Host가 배치될 Public Subnet ID (1개)"
  type        = string
}

variable "private_subnet_id" {
  description = "App Server가 배치될 Private Subnet ID (1개)"
  type        = string
}

variable "sg_bastion_id" {
  description = "Bastion Host용 보안 그룹 ID"
  type        = string
}

variable "sg_app_id" {
  description = "App Server용 보안 그룹 ID"
  type        = string
}

variable "ecr_repository_url" {
  description = "도커 이미지를 가져올 ECR 주소"
  type        = string
}

variable "target_group_arn" {
  description = "ASG가 연결될 ALB 타겟 그룹 ID"
  type        = string
}

variable "key_name" {
  description = "EC2 Key Pair"
  type        = string
}

variable "db_endpoint" { type = string }
variable "db_name" { type = string }
variable "db_username" { type = string }
variable "db_password" { type = string }
variable "s3_bucket_name" { type = string }
variable "cdn_domain" { type = string }
variable "s3_bucket_arn" { type = string }