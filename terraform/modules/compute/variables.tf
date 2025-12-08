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