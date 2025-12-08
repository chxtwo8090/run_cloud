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

  tags = {
    Name = "${var.project_name}-bastion"
  }
}

# 4. App Server 생성 (Private Subnet)
# 참고: NAT Gateway가 없어서 지금 당장은 인터넷이 안 됩니다. (파일 전송은 Bastion 통해 가능)
resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.micro"
  subnet_id              = var.private_subnet_id
  vpc_security_group_ids = [var.sg_app_id]
  key_name               = aws_key_pair.kp.key_name

  tags = {
    Name = "${var.project_name}-app-1"
  }
}