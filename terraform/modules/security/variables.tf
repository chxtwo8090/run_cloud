variable "project_name" { type = string }

variable "vpc_id" {
  description = "보안 그룹이 생성될 VPC ID (Network 모듈에서 받아옴)"
  type        = string
}

variable "admin_ip" {
  description = "관리자(나)의 공인 IP (SSH 접속용)"
  type        = string
}