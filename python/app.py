from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import pymysql, boto3
import datetime
import os
import uuid
import math # [추가] 페이지네이션 계산(올림 처리)을 위해 추가함

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# 환경변수 및 AWS 설정 (기존 유지)
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'runcloud_db')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
CDN_DOMAIN = os.environ.get('CDN_DOMAIN')
AWS_REGION = 'ap-northeast-2'

s3_client = boto3.client('s3', region_name=AWS_REGION)

def get_db_connection():
    # [기존 유지] DB 연결 로직
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
        raise RuntimeError("DB_HOST 환경변수가 없습니다! 로컬 테스트환경을 확인해주세요.")

def init_db():
    if not DB_HOST: return

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # [기존 유지] 사용자 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                            (id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(255),
                            password VARCHAR(255),
                            email VARCHAR(255))''')
            
            # [기존 유지] 러닝 기록 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS runs 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             distance FLOAT, duration INT, date VARCHAR(255))''')
            
            # [변경] 게시판 테이블 구조 변경
            # 변경 이유: 제목(title), 조회수(views), 작성일(created_at) 기능을 지원하기 위함
            # 주의: 기존 테이블이 있다면 이 쿼리로 컬럼이 추가되지 않을 수 있으므로, DB 초기화(DROP TABLE)가 권장됨.
            cursor.execute('''CREATE TABLE IF NOT EXISTS posts 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             title VARCHAR(255), content TEXT, image_url TEXT,
                             views INT DEFAULT 0, 
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # [추가] 댓글 테이블 생성
            # 변경 이유: 게시글에 대한 댓글 저장 공간 확보
            cursor.execute('''CREATE TABLE IF NOT EXISTS comments 
                            (id INT AUTO_INCREMENT PRIMARY KEY, post_id INT, user_id INT,
                             content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
    finally:
        conn.close()

try:
    init_db()
except Exception as e:
    print(f"DB 초기화 실패 (접속 정보 확인 필요): {e}")

# [기존 유지] 회원가입 라우트
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

# [기존 유지] 로그인 라우트
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

# [기존 유지] 대시보드 라우트
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

# [기존 유지] 랭킹 라우트
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

# [변경] 커뮤니티 라우트 (기능 대폭 추가)
@app.route('/community', methods=['GET', 'POST'])
def community():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            # [추가] 제목(title) 입력값 받기
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
                    return f"업로드 에러 발생: {e}"

            # [변경] DB Insert 쿼리에 title, views(0), created_at(NOW()) 추가
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO posts (user_id, title, content, image_url, views, created_at) 
                                  VALUES (%s, %s, %s, %s, 0, NOW())''',
                            (session['user_id'], title, content, image_url))
            conn.commit()
            return redirect(url_for('community'))
            
        # [변경] GET 요청 시: 페이지네이션(Pagination) 로직 적용
        # 이유: 글이 많아졌을 때 한 번에 다 불러오지 않고 끊어서 보여주기 위함
        page = request.args.get('page', 1, type=int)
        limit = 5 # 한 페이지당 보여줄 글 개수
        offset = (page - 1) * limit

        with conn.cursor() as cursor:
            # 1. 전체 글 개수 파악 (총 페이지 수 계산용)
            cursor.execute('SELECT COUNT(*) as count FROM posts')
            total_posts = cursor.fetchone()['count']
            total_pages = math.ceil(total_posts / limit)

            # 2. 현재 페이지에 해당하는 글만 가져오기 (LIMIT, OFFSET 사용)
            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                ORDER BY p.id DESC LIMIT %s OFFSET %s
            ''', (limit, offset))
            posts = cursor.fetchall()
            
    finally:
        conn.close()
    
    # [변경] 템플릿에 현재 페이지(curr_page)와 총 페이지(total_pages) 정보를 함께 전달
    return render_template('community.html', posts=posts, curr_page=page, total_pages=total_pages)

# [추가] 게시글 상세 조회 API (모달용)
# 기능: 게시글 내용과 댓글 목록을 JSON으로 반환하고 조회수를 1 증가시킴
@app.route('/api/post/<int:post_id>')
def get_post_detail(post_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 조회수 증가
            cursor.execute('UPDATE posts SET views = views + 1 WHERE id = %s', (post_id,))
            conn.commit()

            # 2. 게시글 상세 정보 가져오기
            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                WHERE p.id = %s
            ''', (post_id,))
            post = cursor.fetchone()

            # 3. 해당 게시글의 댓글 목록 가져오기
            cursor.execute('''
                SELECT c.*, u.username 
                FROM comments c JOIN users u ON c.user_id = u.id 
                WHERE c.post_id = %s ORDER BY c.id ASC
            ''', (post_id,))
            comments = cursor.fetchall()
            
        return jsonify({'post': post, 'comments': comments})
    finally:
        conn.close()

# [추가] 댓글 등록 API
# 기능: 모달에서 입력한 댓글을 DB에 저장
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

# [기존 유지] 로그아웃
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# [기존 유지] 헬스 체크
@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)