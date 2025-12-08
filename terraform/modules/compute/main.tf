# 1. 최신 Amazon Linux 2023 이미지(AMI) 자동 검색
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# 2. SSH 키 페어 생성 (테라폼이 알아서 만듦)
resource "tls_private_key" "pk" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "kp" {
  key_name   = "${var.project_name}-key"
  public_key = tls_private_key.pk.public_key_openssh
}

# 생성된 비밀키를 내 컴퓨터에 파일로 저장 (로그인할 때 필요함)
resource "local_file" "ssh_key" {
  filename        = "${path.module}/../../${var.project_name}-key.pem"
  content         = tls_private_key.pk.private_key_pem
  file_permission = "0400" # 읽기 전용 권한 설정
}

# 3. Bastion Host 생성 (Public Subnet)
resource "aws_instance" "bastion" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro" # 프리티어
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [var.sg_bastion_id]
  key_name                    = aws_key_pair.kp.key_name
  associate_public_ip_address = true # 공인 IP 자동 할당

  lifecycle {
    ignore_changes = [ami]
  }

  tags = {
    Name = "${var.project_name}-bastion"
  }
}

# # 4. App Server 생성 (Private Subnet)
# # 참고: NAT Gateway가 없어서 지금 당장은 인터넷이 안 됩니다. (파일 전송은 Bastion 통해 가능)
# resource "aws_instance" "app" {
#   ami                    = data.aws_ami.amazon_linux_2023.id
#   instance_type          = "t3.micro"
#   subnet_id              = var.private_subnet_id
#   vpc_security_group_ids = [var.sg_app_id]
#   key_name               = aws_key_pair.kp.key_name

#   tags = {
#     Name = "${var.project_name}-app-1"
#   }
# }

# -----------------------------------------------------------
# 1. IAM Role 설정 (EC2가 ECR에서 이미지를 꺼내오기 위해 필수!)
# -----------------------------------------------------------
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

# ECR 읽기 권한(ReadOnly) 정책을 역할에 붙임
resource "aws_iam_role_policy_attachment" "ecr_readonly" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# 인스턴스 프로파일 (EC2에 역할을 연결하는 껍데기)
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# -----------------------------------------------------------
# 2. Launch Template (서버 찍어내는 틀)
# -----------------------------------------------------------
resource "aws_launch_template" "app" {
  name = "${var.project_name}-template"

  image_id      = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.micro"
  key_name      = aws_key_pair.kp.key_name

  # 네트워크 설정 (보안그룹 연결)
  vpc_security_group_ids = [var.sg_app_id]

  # IAM 권한 연결
  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_profile.name
  }

  # [핵심] 서버가 켜지자마자 실행할 명령어 (User Data)
  # 1. 도커 설치 -> 2. 도커 실행 -> 3. ECR 로그인 -> 4. 이미지 다운 & 실행
user_data = base64encode(<<-EOF
              #!/bin/bash
              dnf update -y
              dnf install -y docker
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ec2-user

              # ECR 로그인
              aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin ${var.ecr_repository_url}

              # [중요] docker run은 딱 한 번만 실행해야 합니다!
              # 모든 환경변수(-e)를 이 명령어 하나에 다 넣으세요.
              docker run -d -p 5000:5000 \
                -e DB_HOST="${replace(var.db_endpoint, ":3306", "")}" \
                -e DB_NAME="${var.db_name}" \
                -e DB_USER="${var.db_username}" \
                -e DB_PASSWORD="${var.db_password}" \
                --restart always \
                ${var.ecr_repository_url}:v2
              EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = { Name = "${var.project_name}-asg-app" }
  }
}

# -----------------------------------------------------------
# 3. Auto Scaling Group (실제 공장 가동)
# -----------------------------------------------------------
resource "aws_autoscaling_group" "app" {
  name                = "${var.project_name}-asg"
  vpc_zone_identifier = [var.private_subnet_id] # Private Subnet에 배치
  
  # ASG 설정: 최소 1대, 최대 3대, 평소 2대 유지
  min_size         = 1
  max_size         = 2
  desired_capacity = 1

  # 사용할 템플릿 지정
  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  # [중요] ALB와 연결! (이게 없으면 로드밸런서가 서버를 못 찾음)
  target_group_arns = [var.target_group_arn]

  tag {
    key                 = "Name"
    value               = "${var.project_name}-asg-instance"
    propagate_at_launch = true
  }
}

