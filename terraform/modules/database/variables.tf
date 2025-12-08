variable "project_name" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "sg_db_id" { type = string }

variable "db_password" {
  description = "DB 마스터 비밀번호"
  type        = string
  sensitive   = true # 로그에 비밀번호가 안 찍히게 가림
}