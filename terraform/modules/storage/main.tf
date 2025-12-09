# 1. 랜덤 문자열 생성 (S3 버킷 이름은 전 세계 유일해야 해서 뒤에 랜덤 값을 붙임)
resource "random_id" "bucket_id" {
  byte_length = 4
}

# 2. S3 버킷 생성 (이미지 원본 저장소)
resource "aws_s3_bucket" "this" {
  bucket        = "${var.project_name}-media-${random_id.bucket_id.hex}"
  force_destroy = true # 실습용: 버킷 안에 파일이 있어도 강제 삭제 허용

  tags = { Name = "${var.project_name}-s3" }
}

# 3. CloudFront 생성 (CDN)
resource "aws_cloudfront_distribution" "this" {
  origin {
    domain_name              = aws_s3_bucket.this.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.this.id
    origin_id                = "S3Origin"
  }

  enabled             = true
  default_root_object = "index.html" # 사실 이미지만 쓸 거라 의미 없지만 필수값

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"] # 읽기 전용
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3Origin"

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # 전 세계 엣지 로케이션 중 가장 싼 곳만 사용 (비용 절감)
  price_class = "PriceClass_100" 

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# 4. OAC (Origin Access Control) 설정
# S3를 직접 열지 않고 CloudFront에게만 문을 열어주는 출입증
resource "aws_cloudfront_origin_access_control" "this" {
  name                              = "${var.project_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# 5. S3 버킷 정책 (Policy)
# "CloudFront 님만 내 파일에 접근할 수 있습니다" 라고 문에 써붙이는 것
resource "aws_s3_bucket_policy" "cdn_access" {
  bucket = aws_s3_bucket.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipal"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.this.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.this.arn
          }
        }
      }
    ]
  })
}