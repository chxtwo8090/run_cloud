resource "aws_acm_certificate" "this" {
  domain_name       = var.domain_name
  validation_method = "DNS" # DNS에 특정 코드를 심어서 주인임을 증명하는 방식

  tags = {
    Name = "${var.project_name}-acm"
  }

  lifecycle {
    create_before_destroy = true
  }
}