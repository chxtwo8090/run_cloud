# 1. 서브넷 그룹 생성 (DB가 위치할 Private Subnet들 묶음)
resource "aws_db_subnet_group" "this" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "${var.project_name}-db-subnet-group" }
}

# 2. RDS 인스턴스 생성 (MySQL)
resource "aws_db_instance" "this" {
  identifier        = "${var.project_name}-db"
  engine            = "mysql"
  engine_version    = "8.0"
  instance_class    = "db.t3.micro" # 프리티어 가능
  allocated_storage = 20            # 20GB (프리티어 최대)
  storage_type      = "gp3"

  # [중요] DB 접속 정보 (나중에 파이썬 코드에 환경변수로 넣어줄 것임)
  db_name  = "runcloud_db" # 초기 생성할 데이터베이스 이름
  username = "admin"
  password = var.db_password # 변수로 받아서 설정 (보안)

  # 네트워크 설정
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.sg_db_id]
  publicly_accessible    = false # 외부 접속 차단 (보안)
  
  # 삭제 방지 설정 (테스트할 땐 false로 해서 빨리 지워지게 함)
  skip_final_snapshot = true
  
  tags = { Name = "${var.project_name}-db" }
}