# 1. VPC 생성 (가상 데이터 센터)
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# 2. 인터넷 게이트웨이 (외부와 통신하는 문)
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# 3. Public 서브넷 (누구나 접근 가능) - 2개 생성 (가용영역 a, c)
resource "aws_subnet" "public" {
  count             = length(var.public_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  
  # 여기서 만든 서버는 자동으로 공인 IP를 받음
  map_public_ip_on_launch = true 

  tags = {
    Name = "${var.project_name}-public-${count.index + 1}"
  }
}

# 4. Private 서브넷 (외부 접근 불가, 보안 강화) - 2개 생성
resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-private-${count.index + 1}"
  }
}

# 5. Public 라우팅 테이블 (인터넷으로 나가는 길 안내)
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.project_name}-rt-public"
  }
}

# 6. Public 서브넷과 라우팅 테이블 연결
resource "aws_route_table_association" "public" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# [추가 1] NAT 게이트웨이가 사용할 고정 IP (EIP)
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

# [추가 2] NAT 게이트웨이 생성 (Public Subnet에 위치해야 함!)
resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id # 첫 번째 Public Subnet에 배치

  tags = {
    Name = "${var.project_name}-nat-gw"
  }

  # IGW가 먼저 만들어져야 NAT도 만들 수 있음
  depends_on = [aws_internet_gateway.this]
}

# [추가 3] Private 라우팅 테이블 (인터넷으로 가는 길을 NAT로 안내)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }

  tags = {
    Name = "${var.project_name}-rt-private"
  }
}

# [추가 4] Private 서브넷과 라우팅 테이블 연결 (이게 없으면 도로가 안 이어짐!)
resource "aws_route_table_association" "private" {
  count          = length(var.private_subnet_cidrs)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}