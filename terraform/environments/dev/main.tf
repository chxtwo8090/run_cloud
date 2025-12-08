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

module "compute" {
  source = "../../modules/compute"

  project_name = "run-cloud"

  # [중요] 서브넷 리스트(List) 중에서 0번째(첫 번째) 서브넷을 골라서 전달
  public_subnet_id  = module.network.public_subnets[0]
  private_subnet_id = module.network.private_subnet_ids[0]

  # Security 모듈에서 만든 보안 그룹 ID 전달
  sg_bastion_id = module.security.sg_bastion_id
  sg_app_id     = module.security.sg_app_id
}