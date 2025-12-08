resource "aws_ecr_repository" "app_repo" {
  name                 = "${var.project_name}-repo"
  image_tag_mutability = "MUTABLE" # 같은 태그(v1)로 덮어쓰기 허용

  # 이미지 스캔 (보안 취약점 검사) 기능을 켭니다
  image_scanning_configuration {
    scan_on_push = true
  }
  
  # 레포지토리 삭제 시 안에 있는 이미지도 강제로 다 지움 (테스트용 옵션)
  force_delete = true 

  tags = {
    Name = "${var.project_name}-repo"
  }
}