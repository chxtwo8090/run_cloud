output "bastion_public_ip" {
  description = "Bastion Host의 접속용 공인 IP"
  value       = aws_instance.bastion.public_ip
}

# output "app_private_ip" {
#   description = "App Server의 내부 IP"
#   value       = aws_instance.app.private_ip
# }

output "asg_name" {
  description = "생성된 Auto Scaling Group 이름"
  value       = aws_autoscaling_group.app.name
}