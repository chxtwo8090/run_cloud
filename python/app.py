from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash
import pymysql, boto3
import datetime
import os
import uuid
import math
from datetime import timedelta 
# [추가] 보안 기능을 위해 werkzeug.security 라이브러리 추가
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# ---------------------------------------------------------
# 환경변수 설정 (Terraform 및 Docker에서 주입받는 값)
# ---------------------------------------------------------
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'runcloud_db')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
CDN_DOMAIN = os.environ.get('CDN_DOMAIN')
AWS_REGION = 'ap-northeast-2'

# S3 클라이언트 생성
s3_client = boto3.client('s3', region_name=AWS_REGION)

def get_db_connection():
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
        # 로컬 테스트 환경이 아닐 경우 에러 발생
        raise RuntimeError("DB_HOST 환경변수가 설정되지 않았습니다.")

def init_db():
    """DB 테이블 초기화 함수"""
    if not DB_HOST: return

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 사용자 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                            (id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(255) NOT NULL UNIQUE,
                            password VARCHAR(255) NOT NULL,
                            email VARCHAR(255) NOT NULL UNIQUE)''')
            
            # 2. 러닝 기록 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS runs 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             distance FLOAT, duration INT, date VARCHAR(255))''')
            
            # 3. 게시판 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS posts 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             title VARCHAR(255), content TEXT, image_url TEXT,
                             views INT DEFAULT 0, 
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # 4. 댓글 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS comments 
                            (id INT AUTO_INCREMENT PRIMARY KEY, post_id INT, user_id INT,
                             content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
    finally:
        conn.close()

# 앱 시작 시 DB 초기화 시도
try:
    init_db()
except Exception as e:
    print(f"DB 초기화 실패 (접속 정보 확인 필요): {e}")

# ---------------------------------------------------------
# [수정] 회원가입 라우트: 비밀번호 암호화 적용
# ---------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 중복 ID 검사
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                if cursor.fetchone():
                    return "이미 존재하는 ID입니다! <a href='/register'>다시 시도</a>"
                
                # 중복 이메일 검사
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                if cursor.fetchone():
                    return "이미 가입된 이메일입니다! <a href='/register'>다시 시도</a>"

                # [보안] 비밀번호를 그대로 저장하지 않고 해시(Hash)화 하여 저장
                hashed_pw = generate_password_hash(password)

                cursor.execute('INSERT INTO users (username, password, email) VALUES (%s, %s, %s)', 
                               (username, hashed_pw, email))
            conn.commit()
        except Exception as e:
            return f"회원가입 에러: {e}"
        finally:
            conn.close()
            
        return redirect(url_for('login'))
        
    return render_template('register.html')

# ---------------------------------------------------------
# [수정] 로그인 라우트: 암호 검증 로직 추가 (자동가입 삭제)
# ---------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 사용자 조회
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
                
                # [보안] 사용자가 존재하고, 비밀번호 해시값이 일치하는지 확인 (check_password_hash)
                # 기존의 '없는 아이디면 자동 가입' 시키는 로직은 보안상 위험하므로 삭제함
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    return redirect(url_for('dashboard'))
                else:
                    # 로그인 실패 처리
                    flash('아이디 또는 비밀번호가 올바르지 않습니다.')
                    return redirect(url_for('login'))
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
            
            # [기능] 한국 시간(KST)으로 저장 (UTC + 9시간)
            kst_now = datetime.datetime.utcnow() + timedelta(hours=9)
            date = kst_now.strftime("%Y-%m-%d %H:%M:%S")
            
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
            title = request.form['title']
            content = request.form['content']
            image_file = request.files['image']
            image_url = ""

            # S3 이미지 업로드 로직
            if image_file and image_file.filename != '':
                ext = image_file.filename.split('.')[-1]
                filename = f"{uuid.uuid4()}.{ext}"
                try:
                    s3_client.upload_fileobj(
                        image_file, S3_BUCKET, filename,
                        ExtraArgs={'ContentType': image_file.content_type}
                    )
                    # CloudFront 도메인이 있으면 사용, 없으면 S3 기본 URL 사용
                    if CDN_DOMAIN:
                        image_url = f"https://{CDN_DOMAIN}/{filename}"
                    else:
                        image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
                except Exception as e:
                    print(f"S3 업로드 실패: {e}")

            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO posts (user_id, title, content, image_url, views, created_at) 
                                  VALUES (%s, %s, %s, %s, 0, NOW())''',
                            (session['user_id'], title, content, image_url))
            conn.commit()
            return redirect(url_for('community'))

        # GET 요청: 게시글 목록 조회 (페이지네이션 적용)
        page = request.args.get('page', 1, type=int)
        limit = 5
        offset = (page - 1) * limit

        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as count FROM posts')
            total_posts = cursor.fetchone()['count']
            total_pages = math.ceil(total_posts / limit)

            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                ORDER BY p.id DESC LIMIT %s OFFSET %s
            ''', (limit, offset))
            posts = cursor.fetchall()
            
            # [기능] 게시글 작성 시간 한국 시간(KST) 변환
            for post in posts:
                if isinstance(post['created_at'], datetime.datetime):
                    kst_time = post['created_at'] + timedelta(hours=9)
                    post['created_at'] = kst_time.strftime('%Y-%m-%d %H:%M')

    finally:
        conn.close()
    
    return render_template('community.html', posts=posts, curr_page=page, total_pages=total_pages)

@app.route('/api/post/<int:post_id>')
def get_post_detail(post_id):
    """게시글 상세 조회 및 댓글 목록 반환 API"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 조회수 증가
            cursor.execute('UPDATE posts SET views = views + 1 WHERE id = %s', (post_id,))
            conn.commit()

            # 게시글 정보 조회
            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                WHERE p.id = %s
            ''', (post_id,))
            post = cursor.fetchone()

            # 상세 조회 시간 KST 변환
            if post and isinstance(post['created_at'], datetime.datetime):
                post['created_at'] = (post['created_at'] + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')

            # 댓글 목록 조회
            cursor.execute('''
                SELECT c.*, u.username 
                FROM comments c JOIN users u ON c.user_id = u.id 
                WHERE c.post_id = %s ORDER BY c.id ASC
            ''', (post_id,))
            comments = cursor.fetchall()
            
            # 댓글 시간 KST 변환
            for c in comments:
                if isinstance(c['created_at'], datetime.datetime):
                    c['created_at'] = (c['created_at'] + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')
            
        return jsonify({'post': post, 'comments': comments})
    finally:
        conn.close()

@app.route('/api/comment', methods=['POST'])
def add_comment():
    """댓글 등록 API"""
    if 'user_id' not in session:
        return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})

    post_id = request.form['post_id']
    content = request.form['content']
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO comments (post_id, user_id, content, created_at) 
                VALUES (%s, %s, %s, NOW())
            ''', (post_id, session['user_id'], content))
        conn.commit()
        return jsonify({'result': 'success'})
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)