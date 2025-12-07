variable "project_name" {
  description = "프로젝트 이름 (태그용)"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC의 IP 대역"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "Public 서브넷들의 IP 대역 리스트"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "Private 서브넷들의 IP 대역 리스트"
  type        = list(string)
}

variable "availability_zones" {
  description = "사용할 가용 영역 (예: ap-northeast-2a)"
  type        = list(string)
}