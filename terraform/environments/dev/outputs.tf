output "vpc_id" {
  description = "생성된 VPC의 ID"
  value       = module.network.vpc_id
}

output "public_subnets" {
  description = "생성된 Public 서브넷들의 ID"
  value       = module.network.public_subnet_ids
}

output "security_group_ids" {
  description = "생성된 보안 그룹 ID 목록"
  value = {
    alb     = module.security.sg_alb_id
    bastion = module.security.sg_bastion_id
    app     = module.security.sg_app_id
    db      = module.security.sg_db_id
  }
}

output "bastion_ssh_command" {
  description = "Bastion Host 접속 명령어"
  value       = "ssh -i run-cloud-key.pem ec2-user@${module.compute.bastion_public_ip}"
}

output "app_server_ip" {
  value = module.compute.app_private_ip
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}