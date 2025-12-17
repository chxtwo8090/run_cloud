# # 1. SSH 키 페어 생성
# resource "tls_private_key" "pk" {
#   algorithm = "RSA"
#   rsa_bits  = 4096
# }

# resource "aws_key_pair" "kp" {
#   key_name   = "${var.project_name}-key"
#   public_key = tls_private_key.pk.public_key_openssh
# }

# resource "local_file" "ssh_key" {
#   filename        = "${path.module}/../../${var.project_name}-key.pem"
#   content         = tls_private_key.pk.private_key_pem
#   file_permission = "0400"
# }

# 2. Bastion Host (이미지 검색 로직 유지 - 배스천은 최신 이미지 써도 무방)
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

resource "aws_instance" "bastion" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro"
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [var.sg_bastion_id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  tags = {
    Name = "${var.project_name}-bastion"
  }
}

# 3. IAM Role 설정
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

resource "aws_iam_policy" "s3_upload" {
  name        = "${var.project_name}-s3-upload-policy"
  description = "Allow EC2 to upload images to S3"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
        Resource = "${var.s3_bucket_arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_upload.arn
}

resource "aws_iam_role_policy_attachment" "ecr_readonly" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# -----------------------------------------------------------
# 4. Launch Template (AMI 교체 및 User Data 수정)
# -----------------------------------------------------------
resource "aws_launch_template" "app" {
  name = "${var.project_name}-template"

  # [중요] 여기에 찬규님이 만든 AMI ID를 입력하세요! (예: ami-0ab...)
  image_id      = "ami-0e96ceefd7f932989" 
  
  instance_type = "t3.micro"
  key_name      = var.key_name
  vpc_security_group_ids = [var.sg_app_id]

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_profile.name
  }

  # [수정] 도커 설치 과정 삭제 (이미지에 포함됨) -> 실행만 하면 됨
  user_data = base64encode(<<-EOF
              #!/bin/bash
              # 도커 서비스 시작 (이미 설치되어 있음)
              systemctl start docker
              systemctl enable docker
              
              # ECR 로그인 및 컨테이너 실행
              aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin ${var.ecr_repository_url}
              
              until docker pull ${var.ecr_repository_url}:latest; do
                echo "이미지 다운로드 재시도..."
                sleep 5
              done

              docker run -d -p 5000:5000 \
                -e DB_HOST="${replace(var.db_endpoint, ":3306", "")}" \
                -e DB_NAME="${var.db_name}" \
                -e DB_USER="${var.db_username}" \
                -e DB_PASSWORD="${var.db_password}" \
                -e S3_BUCKET_NAME="${var.s3_bucket_name}" \
                -e CDN_DOMAIN="${var.cdn_domain}" \
                --restart always \
                ${var.ecr_repository_url}:latest
              EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = { Name = "${var.project_name}-asg-app" }
  }
}

# 5. Auto Scaling Group
resource "aws_autoscaling_group" "app" {
  name                = "${var.project_name}-asg"
  vpc_zone_identifier = [var.private_subnet_id]
  
  min_size         = 1
  max_size         = 1
  desired_capacity = 1

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  target_group_arns = [var.target_group_arn]

  tag {
    key                 = "Name"
    value               = "${var.project_name}-asg-instance"
    propagate_at_launch = true
  }
}
