output "alb_dns_name" {
  description = "웹 브라우저 접속용 주소"
  value       = aws_lb.this.dns_name
}

output "target_group_arn" {
  description = "ASG와 연결할 타겟 그룹 ID"
  value       = aws_lb_target_group.this.arn
}