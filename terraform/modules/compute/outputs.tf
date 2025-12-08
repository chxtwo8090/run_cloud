output "bastion_public_ip" {
  description = "Bastion Host의 접속용 공인 IP"
  value       = aws_instance.bastion.public_ip
}

output "app_private_ip" {
  description = "App Server의 내부 IP"
  value       = aws_instance.app.private_ip
}