output "acm_certificate_arn" {
  value = aws_acm_certificate_validation.this.certificate_arn
}

output "route53_zone_id" {
  value = aws_route53_zone.this.zone_id
}