from flask import Flask, render_template, request, redirect, session, url_for
import pymysql,boto3
import datetime
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# 환경변수에서 DB 접속 정보 가져오기 (Terraform이 넣어줄 값들)
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'runcloud_db')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
CDN_DOMAIN = os.environ.get('CDN_DOMAIN')
AWS_REGION = 'ap-northeast-2'

# S3 클라이언트 생성 (IAM Role 덕분에 키/비밀번호 없이 권한 획득!)
s3_client = boto3.client('s3', region_name=AWS_REGION)

def get_db_connection():
    # 1. 환경변수에 DB 주소가 있으면 -> AWS RDS (MySQL) 접속
    if DB_HOST:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    else:
        # 2. 없으면 -> 로컬 테스트용 (가짜 연결 객체 반환하거나 에러 처리)
        # (여기서는 간단히 에러 메시지 출력)
        raise RuntimeError("DB_HOST 환경변수가 없습니다! 로컬 테스트라면 sqlite 코드를 유지해야 하지만, 실습 편의상 생략합니다.")

def init_db():
    # RDS는 이미 만들어져 있으므로 테이블 생성 쿼리만 날림
    if not DB_HOST: return # 로컬이면 패스

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 사용자 테이블
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                        (id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255),
                        password VARCHAR(255),
                       email VARCHAR(255))''')
        # 러닝 기록 테이블
        cursor.execute('''CREATE TABLE IF NOT EXISTS runs 
                        (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                         distance FLOAT, duration INT, date VARCHAR(255))''')
        # 게시판 테이블
        cursor.execute('''CREATE TABLE IF NOT EXISTS posts 
                        (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                         content TEXT, image_url TEXT)''')
    conn.commit()
    conn.close()

# 앱 시작 시 테이블 생성 (주의: 실무에선 배포 파이프라인에서 따로 함)
try:
    init_db()
except Exception as e:
    print(f"DB 초기화 실패 (접속 정보 확인 필요): {e}")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # [수정] HTML 폼에서 보내준 값들을 각각 받습니다.
        username = request.form['username']  # ID 입력값
        email = request.form['email']        # 이메일 입력값
        password = request.form['password']  # 비밀번호 입력값
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. ID 중복 확인
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                if cursor.fetchone():
                    return "이미 존재하는 ID입니다! <a href='/register'>다시 시도</a>"
                
                # [추가] 이메일 중복 확인 (선택사항)
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                if cursor.fetchone():
                    return "이미 가입된 이메일입니다! <a href='/register'>다시 시도</a>"

                # 2. DB에 저장 (ID, 비밀번호, 이메일 모두 저장)
                cursor.execute('INSERT INTO users (username, password, email) VALUES (%s, %s, %s)', 
                               (username, password, email))
            conn.commit()
        except Exception as e:
            return f"회원가입 에러: {e}"
        finally:
            conn.close()
            
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
                
                if not user:
                    cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, '1234'))
                    conn.commit()
                    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                    user = cursor.fetchone()
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        finally:
            conn.close()
            
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            distance = request.form['distance']
            duration = request.form['duration']
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO runs (user_id, distance, duration, date) VALUES (%s, %s, %s, %s)',
                            (session['user_id'], distance, duration, date))
            conn.commit()
            
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM runs WHERE user_id = %s ORDER BY id DESC', (session['user_id'],))
            my_runs = cursor.fetchall()
    finally:
        conn.close()
    
    return render_template('dashboard.html', username=session['username'], runs=my_runs)

@app.route('/ranking')
def ranking():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.username, SUM(r.distance) as total_dist 
                FROM runs r JOIN users u ON r.user_id = u.id 
                GROUP BY u.id ORDER BY total_dist DESC LIMIT 10
            ''')
            ranks = cursor.fetchall()
    finally:
        conn.close()
    
    return render_template('ranking.html', ranks=ranks)

@app.route('/community', methods=['GET', 'POST'])
def community():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            content = request.form['content']
            image_file = request.files['image'] # HTML에서 file 타입으로 보낸 것 받기
            
            image_url = "" # 이미지가 없을 경우 빈 값

            # 사용자가 이미지를 올렸다면?
            if image_file and image_file.filename != '':
                # 1. 파일 이름 안전하게 변경 (랜덤 UUID 사용)
                ext = image_file.filename.split('.')[-1]
                filename = f"{uuid.uuid4()}.{ext}"
                
                try:
                    # 2. S3 버킷에 업로드
                    # (ContentType을 설정해야 브라우저에서 바로 보입니다)
                    s3_client.upload_fileobj(
                        image_file,
                        S3_BUCKET,
                        filename,
                        ExtraArgs={'ContentType': image_file.content_type}
                    )
                    
                    # 3. 이미지 주소 생성 (CDN 도메인 사용)
                    # CDN 도메인이 없으면 S3 기본 주소 사용 (비상용)
                    if CDN_DOMAIN:
                        image_url = f"https://{CDN_DOMAIN}/{filename}"
                    else:
                        image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
                        
                except Exception as e:
                    print(f"S3 업로드 실패: {e}")
                    return f"업로드 에러 발생: {e}"

            # DB에 저장 (이미지 URL 포함)
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO posts (user_id, content, image_url) VALUES (%s, %s, %s)',
                            (session['user_id'], content, image_url))
            conn.commit()
            
        with conn.cursor() as cursor:
            cursor.execute('SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id ORDER BY p.id DESC')
            posts = cursor.fetchall()
    finally:
        conn.close()
    
    return render_template('community.html', posts=posts)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)