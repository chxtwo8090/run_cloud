# 1. 가볍고 안정적인 파이썬 3.9 버전을 베이스로 사용
FROM python:3.11-slim

# 2. 컨테이너 내에서 작업할 폴더 생성 및 설정
WORKDIR /app

# 3. 라이브러리 목록 파일 먼저 복사 (캐싱 효율을 위해)
COPY requirements.txt .

# 4. 라이브러리 설치
RUN pip install --no-cache-dir -r requirements.txt

# 5. 나머지 소스 코드 전체 복사
COPY . .

# 6. 컨테이너가 5000번 포트를 쓴다는 것을 명시
EXPOSE 5000

# 7. 컨테이너가 시작될 때 실행할 명령어
CMD ["python", "app.py"]