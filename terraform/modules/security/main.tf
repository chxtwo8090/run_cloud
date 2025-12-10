# 1. ALB용 보안 그룹 (인터넷 -> ALB)
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-sg-alb"
  description = "Allow HTTP/HTTPS from Internet"
  vpc_id      = var.vpc_id

  # 인바운드: 전 세계 어디서나 웹 접속 허용
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # 아웃바운드: 나가는 건 모두 허용
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg-alb" }
}

# 2. Bastion용 보안 그룹 (관리자 -> Bastion)
resource "aws_security_group" "bastion" {
  name        = "${var.project_name}-sg-bastion"
  description = "Allow SSH from Admin"
  vpc_id      = var.vpc_id

  # 인바운드: 오직 관리자 IP에서만 SSH(22) 허용
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_ip] 
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg-bastion" }
}

# 3. App(EC2)용 보안 그룹 (ALB/Bastion -> App)
resource "aws_security_group" "app" {
  name        = "${var.project_name}-sg-app"
  description = "Allow traffic from ALB and Bastion"
  vpc_id      = var.vpc_id

  # 규칙 1: ALB에서 오는 웹 트래픽 허용 (포트 5000: Flask)
  ingress {
    from_port       = 5000
    to_port         = 5000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id] # 중요! CIDR이 아니라 SG ID를 참조
  }

  # 규칙 2: Bastion에서 오는 SSH 트래픽 허용
  ingress {
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [aws_security_group.bastion.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg-app" }
}

# 4. DB용 보안 그룹 (App -> DB)
resource "aws_security_group" "db" {
  name        = "${var.project_name}-sg-db"
  description = "Allow traffic from App"
  vpc_id      = var.vpc_id

  # 규칙: App 서버에서 오는 DB 접속만 허용
  ingress {
    from_port       = 3306 # MySQL 포트 (필요 시 변경)
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  
  # Redis용 포트도 열어둡니다
   ingress {
    from_port       = 6379 
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg-db" }
}