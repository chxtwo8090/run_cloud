# 1. 로드 밸런서 본체 생성
resource "aws_lb" "this" {
  name               = "${var.project_name}-alb"
  internal           = false           # 외부(Internet)에서 접속 가능하게 설정
  load_balancer_type = "application"   # HTTP/HTTPS 처리에 적합한 ALB 선택
  security_groups    = [var.sg_alb_id] # Security 모듈에서 만든 ALB용 보안그룹 연결
  subnets            = var.public_subnet_ids # Public Subnet에 배치 (중요!)

  tags = {
    Name = "${var.project_name}-alb"
  }
}

# 2. 타겟 그룹 생성 (요청을 넘겨받을 서버들의 그룹)
resource "aws_lb_target_group" "this" {
  name        = "${var.project_name}-tg"
  port        = 5000               # 플라스크 앱 포트
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"         # EC2 인스턴스를 대상으로 함

  # 헬스 체크: 서버가 살아있는지 주기적으로 찔러보는 설정
  health_check {
    path                = "/"      # 접속해볼 경로 (메인 페이지)
    protocol            = "HTTP"
    matcher             = "200"    # 200 OK 응답이 오면 정상으로 판단
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

# # 3. 리스너 생성 (문지기)
# # 사용자가 80포트(HTTP)로 들어오면 -> 타겟 그룹으로 넘겨라
# resource "aws_lb_listener" "http" {
#   load_balancer_arn = aws_lb.this.arn
#   port              = 80
#   protocol          = "HTTP"

#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.this.arn
#   }
# }

# 1. [수정] HTTP(80) 리스너 -> HTTPS로 강제 리다이렉트
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# 2. [추가] HTTPS(443) 리스너
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08" # 기본 보안 정책
  certificate_arn   = var.acm_certificate_arn     # 모듈에서 넘겨받을 인증서

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

# 3. [추가] Route 53 레코드 (도메인 -> ALB 연결 자동화)
resource "aws_route53_record" "www" {
  zone_id = var.route53_zone_id # ACM 모듈에서 만든 Zone ID
  name    = var.domain_name     # 예: chankyu.com
  type    = "A"                 # Alias(별칭) 레코드

  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}