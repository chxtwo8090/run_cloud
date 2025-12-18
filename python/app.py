from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash
import pymysql, boto3
import datetime
import os
import uuid
import math
from datetime import timedelta 
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# ---------------------------------------------------------
# 환경변수 설정
# ---------------------------------------------------------
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'runcloud_db')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
CDN_DOMAIN = os.environ.get('CDN_DOMAIN')
AWS_REGION = 'ap-northeast-2'

s3_client = boto3.client('s3', region_name=AWS_REGION)

def get_db_connection():
    if DB_HOST:
        conn = pymysql.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME,
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    else:
        raise RuntimeError("DB_HOST 환경변수가 설정되지 않았습니다.")

def init_db():
    if not DB_HOST: return
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                            (id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(255) NOT NULL UNIQUE,
                            password VARCHAR(255) NOT NULL,
                            email VARCHAR(255) NOT NULL UNIQUE)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS runs 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             distance FLOAT, duration INT, date VARCHAR(255))''')
            
            # [스키마 반영] 이미 ALTER로 추가했지만, 코드상 명시를 위해 포함
            cursor.execute('''CREATE TABLE IF NOT EXISTS posts 
                            (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, 
                             category VARCHAR(50) DEFAULT 'free',
                             title VARCHAR(255), content TEXT, image_url TEXT,
                             views INT DEFAULT 0, 
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             is_deleted BOOLEAN DEFAULT FALSE)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS comments 
                            (id INT AUTO_INCREMENT PRIMARY KEY, post_id INT, user_id INT,
                             content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
    finally:
        conn.close()

try:
    init_db()
except Exception as e:
    print(f"DB 초기화 실패: {e}")

# ---------------------------------------------------------
# 라우트 정의
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
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                if cursor.fetchone(): return "이미 존재하는 ID입니다!"
                
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                if cursor.fetchone(): return "이미 가입된 이메일입니다!"

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

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    return redirect(url_for('dashboard'))
                else:
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
        # 기록 저장 로직
        if request.method == 'POST':
            distance = request.form['distance']
            duration = request.form['duration']
            
            kst_now = datetime.datetime.utcnow() + timedelta(hours=9)
            date = kst_now.strftime("%Y-%m-%d %H:%M:%S")
            
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO runs (user_id, distance, duration, date) VALUES (%s, %s, %s, %s)',
                            (session['user_id'], distance, duration, date))
            conn.commit()
            
        with conn.cursor() as cursor:
            # 1. 내 기록 가져오기
            cursor.execute('SELECT * FROM runs WHERE user_id = %s ORDER BY id DESC', (session['user_id'],))
            my_runs = cursor.fetchall()
            
            # 2. 누적 거리 계산
            total_km = sum(run['distance'] for run in my_runs)
            total_km = round(total_km, 2)
            
            # 3. 내 랭킹 계산
            cursor.execute('''
                SELECT user_id, SUM(distance) as total_dist 
                FROM runs 
                GROUP BY user_id 
                ORDER BY total_dist DESC
            ''')
            all_ranks = cursor.fetchall()
            
            my_rank = "-"
            for index, rank_info in enumerate(all_ranks):
                if rank_info['user_id'] == session['user_id']:
                    my_rank = index + 1
                    break
            
            # 4. [그래프용] 월별 통계 데이터 가공
            monthly_stats = {}
            for run in my_runs:
                month_key = run['date'][:7] # YYYY-MM 추출
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = 0
                monthly_stats[month_key] += run['distance']
            
            # 월 순서대로 정렬
            sorted_months = sorted(monthly_stats.keys())
            chart_labels = sorted_months
            chart_data = [round(monthly_stats[m], 2) for m in sorted_months]

    finally:
        conn.close()
    
    # 템플릿에 차트 데이터 전달
    return render_template('dashboard.html', 
                           username=session['username'], 
                           runs=my_runs, 
                           my_rank=my_rank, 
                           total_km=total_km,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

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
            category = request.form.get('category', 'free')
            title = request.form['title']
            content = request.form['content']
            image_file = request.files['image']
            image_url = ""

            if image_file and image_file.filename != '':
                ext = image_file.filename.split('.')[-1]
                filename = f"{uuid.uuid4()}.{ext}"
                try:
                    s3_client.upload_fileobj(image_file, S3_BUCKET, filename, ExtraArgs={'ContentType': image_file.content_type})
                    if CDN_DOMAIN: image_url = f"https://{CDN_DOMAIN}/{filename}"
                    else: image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
                except Exception as e: print(f"S3 업로드 실패: {e}")

            with conn.cursor() as cursor:
                # [작성] is_deleted는 기본값이 FALSE이므로 별도 지정 불필요
                cursor.execute('''INSERT INTO posts (user_id, category, title, content, image_url, views, created_at) 
                                  VALUES (%s, %s, %s, %s, %s, 0, NOW())''',
                            (session['user_id'], category, title, content, image_url))
            conn.commit()
            return redirect(url_for('community', category=category))

        page = request.args.get('page', 1, type=int)
        category = request.args.get('category', 'free')
        limit = 5
        offset = (page - 1) * limit

        with conn.cursor() as cursor:
            # [조회] 삭제되지 않은 글만 카운트 (Soft Delete 적용)
            cursor.execute('SELECT COUNT(*) as count FROM posts WHERE category = %s AND is_deleted = FALSE', (category,))
            total_posts = cursor.fetchone()['count']
            total_pages = math.ceil(total_posts / limit)

            # [조회] 삭제되지 않은 글만 목록에 표시
            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                WHERE p.category = %s AND p.is_deleted = FALSE
                ORDER BY p.id DESC LIMIT %s OFFSET %s
            ''', (category, limit, offset))
            posts = cursor.fetchall()
            
            for post in posts:
                if isinstance(post['created_at'], datetime.datetime):
                    kst_time = post['created_at'] + timedelta(hours=9)
                    post['created_at'] = kst_time.strftime('%Y-%m-%d %H:%M')
    finally:
        conn.close()
    return render_template('community.html', posts=posts, curr_page=page, total_pages=total_pages, curr_category=category)

@app.route('/api/post/<int:post_id>')
def get_post_detail(post_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # [상세] 삭제된 글은 조회되지 않도록 처리
            cursor.execute('''
                SELECT p.*, u.username 
                FROM posts p JOIN users u ON p.user_id = u.id 
                WHERE p.id = %s AND p.is_deleted = FALSE
            ''', (post_id,))
            post = cursor.fetchone()

            if post:
                # 조회수 증가
                cursor.execute('UPDATE posts SET views = views + 1 WHERE id = %s', (post_id,))
                conn.commit()

                if isinstance(post['created_at'], datetime.datetime):
                    post['created_at'] = (post['created_at'] + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')
                
                # [권한] 현재 접속자가 작성자인지 확인 (프론트엔드 버튼 노출용)
                current_user_id = session.get('user_id')
                post['is_owner'] = (current_user_id == post['user_id'])
            
            # 댓글 가져오기
            cursor.execute('''SELECT c.*, u.username FROM comments c JOIN users u ON c.user_id = u.id WHERE c.post_id = %s ORDER BY c.id ASC''', (post_id,))
            comments = cursor.fetchall()
            for c in comments:
                if isinstance(c['created_at'], datetime.datetime):
                    c['created_at'] = (c['created_at'] + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')
        
        return jsonify({'post': post, 'comments': comments})
    finally:
        conn.close()

# ---------------------------------------------------------
# [기능 추가] 게시글 수정 API
# ---------------------------------------------------------
@app.route('/api/post/edit', methods=['POST'])
def edit_post():
    if 'user_id' not in session: return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})

    post_id = request.form['post_id']
    title = request.form['title']
    content = request.form['content']
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 작성자 본인 확인
            cursor.execute('SELECT user_id FROM posts WHERE id = %s', (post_id,))
            post = cursor.fetchone()
            
            if not post or post['user_id'] != session['user_id']:
                return jsonify({'result': 'fail', 'msg': '권한이 없습니다.'})

            # 내용 업데이트
            cursor.execute('UPDATE posts SET title = %s, content = %s WHERE id = %s', 
                           (title, content, post_id))
        conn.commit()
        return jsonify({'result': 'success'})
    finally:
        conn.close()

# ---------------------------------------------------------
# [기능 추가] 게시글 삭제 API (Soft Delete)
# ---------------------------------------------------------
@app.route('/api/post/delete', methods=['POST'])
def delete_post():
    if 'user_id' not in session: return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})

    post_id = request.form['post_id']
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT user_id FROM posts WHERE id = %s', (post_id,))
            post = cursor.fetchone()
            
            if not post: return jsonify({'result': 'fail', 'msg': '게시글이 없습니다.'})
            if post['user_id'] != session['user_id']:
                return jsonify({'result': 'fail', 'msg': '작성자만 삭제할 수 있습니다.'})

            # [Soft Delete] 실제로 지우지 않고 플래그만 변경
            cursor.execute('UPDATE posts SET is_deleted = TRUE WHERE id = %s', (post_id,))
        conn.commit()
        return jsonify({'result': 'success'})
    finally:
        conn.close()

@app.route('/api/comment', methods=['POST'])
def add_comment():
    if 'user_id' not in session: return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})
    post_id = request.form['post_id']
    content = request.form['content']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO comments (post_id, user_id, content, created_at) VALUES (%s, %s, %s, NOW())''', (post_id, session['user_id'], content))
        conn.commit()
        return jsonify({'result': 'success'})
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/health')
def health(): return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)