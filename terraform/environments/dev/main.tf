terraform {
  # [핵심] 상태 파일을 로컬이 아닌 S3에 저장하겠다는 설정
  backend "s3" {
    bucket = "chxtwo.state" # 방금 만든 버킷 이름!
    key    = "dev/terraform.tfstate"     # 버킷 안에서의 파일 경로
    region = "ap-northeast-2"
  }
}
# 1. 테라폼 설정 및 Provider 지정
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# 찬규님! 여기가 바로 Provider가 들어가는 곳입니다.
provider "aws" {
  region = "ap-northeast-2"  # 서울 리전
}

# 2. 우리가 만든 네트워크 모듈 가져오기 (Module Call)
module "network" {
  source = "../../modules/network"  # 모듈 파일이 있는 상대 경로

  # 모듈에 정의된 변수(variables.tf)들에 값을 채워줍니다.
  project_name         = "run-cloud"
  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
  availability_zones   = ["ap-northeast-2a", "ap-northeast-2c"]
}

module "security" {
  source = "../../modules/security"

  project_name = "run-cloud"
  
  # Network 모듈이 만든 VPC ID를 그대로 물려줍니다 (의존성)
  vpc_id       = module.network.vpc_id
  
  # [중요] 찬규님의 공인 IP 뒤에 /32를 꼭 붙이세요!
  # 예: "221.10.5.123/32"
  admin_ip     = "61.108.4.50/32" # FIXME: 실제 본인 IP로 바꾸세요! (보안상 필수)
}

module "storage" {
  source       = "../../modules/storage"
  project_name = "run-cloud"
}

module "compute" {
  source = "../../modules/compute"

  project_name = "run-cloud"

  # [중요] 서브넷 리스트(List) 중에서 0번째(첫 번째) 서브넷을 골라서 전달
  public_subnet_id  = module.network.public_subnet_ids[0]
  private_subnet_id = module.network.private_subnet_ids[0]

  # Security 모듈에서 만든 보안 그룹 ID 전달
  sg_bastion_id = module.security.sg_bastion_id
  sg_app_id     = module.security.sg_app_id

  # [추가] 새로 생긴 변수들 전달
  ecr_repository_url = module.ecr.repository_url # ECR 모듈에서 받아옴
  target_group_arn   = module.alb.target_group_arn # ALB 모듈에서 받아옴

  # [추가] Database 모듈에서 나온 정보 전달
  db_endpoint = module.database.db_endpoint
  db_name     = "runcloud_db"
  db_username = "admin"
  db_password = "mypassword1234!" # 변수 처리 권장하지만 실습용으론 문자열

  # [추가] 앱이 알아야 할 S3/CDN 정보 전달
  s3_bucket_name = module.storage.s3_bucket_name
  cdn_domain     = module.storage.cloudfront_domain_name
  s3_bucket_arn  = module.storage.s3_bucket_arn # 권한 설정용
}

module "ecr" {
  source = "../../modules/ecr"
  project_name = "run-cloud"
}

module "alb" {
  source = "../../modules/alb"

  project_name      = "run-cloud"
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids # Public Subnet에 둬야 합니다!
  sg_alb_id         = module.security.sg_alb_id
  # [추가] 도메인 & 인증서 정보 전달
  domain_name         = "chxtwo.com"
  acm_certificate_arn = module.acm.acm_certificate_arn
  route53_zone_id     = module.acm.route53_zone_id
}

module "database" {
  source = "../../modules/database"

  project_name       = "run-cloud"
  private_subnet_ids = module.network.private_subnet_ids
  sg_db_id           = module.security.sg_db_id
  
  # 실무에서는 이렇게 비밀번호를 코드에 적으면 안 되지만(Secrets Manager 사용), 
  # 포트폴리오/실습용으로는 간단하게 문자열로 넣겠습니다.
  db_password        = "mypassword1234!" 
}

# 1. ACM 모듈 (도메인 입력)
module "acm" {
  source       = "../../modules/acm"
  project_name = "run-cloud"
  domain_name  = "chxtwo.com" # [실제 구매한 도메인 입력]
}