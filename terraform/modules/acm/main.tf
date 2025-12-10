# 1. 호스팅 영역(Zone) 정보 가져오기 (이미 만들어져 있다고 가정하거나 생성)
# 실습 편의상 여기서 Data로 가져오지 않고, 리소스를 관리하는 게 좋습니다.
# 하지만 보통 Zone은 수동으로 만들거나 별도 모듈로 뺍니다.
# 여기서는 편의상 "Route 53 Zone"도 같이 정의하겠습니다.

resource "aws_route53_zone" "this" {
  name = var.domain_name
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
  zone_id         = aws_route53_zone.this.zone_id
}

# 4. 검증 완료 대기 (테라폼이 "발급됨" 뜰 때까지 기다려줌)
resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}