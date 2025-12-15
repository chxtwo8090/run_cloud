# 1. 도메인 호스팅 영역(Zone) 정보 가져오기
# (이미 Route 53에 도메인이 있다고 가정)
data "aws_route53_zone" "this" {
  name         = var.domain_name
  private_zone = false
}

# 2. 인증서 발급 요청
resource "aws_acm_certificate" "this" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  # 서브도메인(*.chankyu.com)도 커버하고 싶으면 아래 주석 해제
  # subject_alternative_names = ["*.${var.domain_name}"]

  tags = {
    Name = "${var.project_name}-acm"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# 3. [핵심] 검증용 DNS 레코드 자동 생성 (사람 손 필요 없음!)
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.this.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.this.zone_id
}

# 4. 검증 완료 대기 (테라폼이 "발급됨" 뜰 때까지 기다려줌)
resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}
 