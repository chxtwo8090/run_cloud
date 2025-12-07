output "vpc_id" {
  description = "생성된 VPC의 ID"
  value       = module.network.vpc_id
}

output "public_subnets" {
  description = "생성된 Public 서브넷들의 ID"
  value       = module.network.public_subnet_ids
}