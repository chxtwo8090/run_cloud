from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import pymysql, boto3
import datetime
import os
import uuid
import math
from datetime import timedelta # [추가] 한국 시간(KST) 계산을 위해 추가

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
        raise RuntimeError("DB_HOST 환경변수가 없습니다! 로컬 테스트라면 sqlite 코드를 유지해야 하지만, 실습 편의상 생략합니다.")

def init_db():
    if not DB_HOST: return

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # [수정] 게시판 기능 확장을 위해 기존 테이블 삭제 후 재생성 (개발 단계이므로 DROP 사용)
            # 이유: 기존 posts 테이블에는 title, views 컬럼이 없어서 에러가 발생함
            cursor.execute('DROP TABLE IF EXISTS comments')
            cursor.execute('DROP TABLE IF EXISTS posts')

            # 사용자 테이블 (기존 유지)
            cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                            (id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(255),
                            password VARCHAR(255),
                            email VARCHAR(255))''')
            
            # 러닝 기록 테이블 (기존 유지)
            cursor.execute('''CREATE TABLE IF NOT EXISTS runs 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             distance FLOAT, duration INT, date VARCHAR(255))''')
            
            # [재생성] 게시판 테이블 (제목, 조회수, 작성일 추가)
            cursor.execute('''CREATE TABLE IF NOT EXISTS posts 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             title VARCHAR(255), content TEXT, image_url TEXT,
                             views INT DEFAULT 0, 
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # [재생성] 댓글 테이블 (신규 추가)
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                if cursor.fetchone():
                    return "이미 존재하는 ID입니다! <a href='/register'>다시 시도</a>"
                
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                if cursor.fetchone():
                    return "이미 가입된 이메일입니다! <a href='/register'>다시 시도</a>"

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

# [수정] 커뮤니티 라우트: 제목 저장, 페이지네이션, 한국 시간 적용
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

            if image_file and image_file.filename != '':
                ext = image_file.filename.split('.')[-1]
                filename = f"{uuid.uuid4()}.{ext}"
                try:
                    s3_client.upload_fileobj(
                        image_file, S3_BUCKET, filename,
                        ExtraArgs={'ContentType': image_file.content_type}
                    )
                    if CDN_DOMAIN:
                        image_url = f"https://{CDN_DOMAIN}/{filename}"
                    else:
                        image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
                except Exception as e:
                    print(f"S3 업로드 실패: {e}")

            with conn.cursor() as cursor:
                # views는 0, created_at은 DB 서버 시간(NOW())으로 저장
                cursor.execute('''INSERT INTO posts (user_id, title, content, image_url, views, created_at) 
                                  VALUES (%s, %s, %s, %s, 0, NOW())''',
                            (session['user_id'], title, content, image_url))
            conn.commit()
            return redirect(url_for('community'))

        # GET 요청 처리 (목록 조회)
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
            
            # [추가] 한국 시간(KST) 변환 로직
            # DB에 저장된 시간(UTC)에 9시간을 더해서 포맷팅함
            for post in posts:
                if isinstance(post['created_at'], datetime.datetime):
                    kst_time = post['created_at'] + timedelta(hours=9)
                    post['created_at'] = kst_time.strftime('%Y-%m-%d %H:%M')

    finally:
        conn.close()
    
    return render_template('community.html', posts=posts, curr_page=page, total_pages=total_pages)

# [추가] 게시글 상세 조회 API (모달용) - 한국 시간 적용
@app.route('/api/post/<int:post_id>')
def get_post_detail(post_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE posts SET views = views + 1 WHERE id = %s', (post_id,))
            conn.commit()

            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                WHERE p.id = %s
            ''', (post_id,))
            post = cursor.fetchone()

            # 게시글 시간 KST 변환
            if post and isinstance(post['created_at'], datetime.datetime):
                post['created_at'] = (post['created_at'] + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')

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

# [추가] 댓글 등록 API
@app.route('/api/comment', methods=['POST'])
def add_comment():
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