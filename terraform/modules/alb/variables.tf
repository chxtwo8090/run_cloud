variable "project_name" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "sg_alb_id" { type = string }
variable "domain_name" { type = string }
variable "acm_certificate_arn" { type = string }
variable "route53_zone_id" { type = string }