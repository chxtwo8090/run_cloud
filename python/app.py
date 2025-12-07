from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import datetime
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # 세션 암호화 키

# --- [DB 설정] 나중에 AWS RDS 주소로 바뀔 부분 ---
def get_db_connection():
    # 지금은 로컬 파일 DB(database.db)를 사용합니다.
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- [초기화] 테이블이 없으면 생성 ---
def init_db():
    conn = get_db_connection()
    # 사용자 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')
    # 러닝 기록 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS runs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                     distance REAL, duration INTEGER, date TEXT)''')
    # 게시판 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS posts 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                     content TEXT, image_url TEXT)''')
    conn.commit()
    conn.close()

# 앱 시작 시 DB 초기화
init_db()

# 1. 메인/로그인 페이지
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        # 간단한 로직: ID만 입력하면 로그인/가입 처리
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if not user:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, '1234'))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        conn.close()
        session['user_id'] = user['id']
        session['username'] = user['username']
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

# 2. 대시보드 (기록 저장) - 나중에 SQS 연동 포인트!
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        distance = request.form['distance']
        duration = request.form['duration']
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # [핵심] 지금은 DB에 바로 넣지만, 나중엔 여기서 SQS로 메시지를 보낼 겁니다.
        conn = get_db_connection()
        conn.execute('INSERT INTO runs (user_id, distance, duration, date) VALUES (?, ?, ?, ?)',
                     (session['user_id'], distance, duration, date))
        conn.commit()
        conn.close()
        
    # 내 기록 조회
    conn = get_db_connection()
    my_runs = conn.execute('SELECT * FROM runs WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('dashboard.html', username=session['username'], runs=my_runs)

# 3. 랭킹 페이지 - 나중에 Redis 연동 포인트!
@app.route('/ranking')
def ranking():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # [핵심] 지금은 DB에서 Sum/Sort 하지만, 나중엔 Redis Sorted Set에서 가져올 겁니다.
    conn = get_db_connection()
    # 사용자별 총 뛴 거리 합산 쿼리
    ranks = conn.execute('''
        SELECT u.username, SUM(r.distance) as total_dist 
        FROM runs r JOIN users u ON r.user_id = u.id 
        GROUP BY u.id ORDER BY total_dist DESC LIMIT 10
    ''').fetchall()
    conn.close()
    
    return render_template('ranking.html', ranks=ranks)

# 4. 커뮤니티 - 나중에 S3 연동 포인트!
@app.route('/community', methods=['GET', 'POST'])
def community():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        content = request.form['content']
        # [핵심] 파일 업로드는 여기서 S3 boto3 코드로 대체될 예정
        image_url = "https://via.placeholder.com/150" # 임시 이미지
        
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (user_id, content, image_url) VALUES (?, ?, ?)',
                     (session['user_id'], content, image_url))
        conn.commit()
        conn.close()
        
    conn = get_db_connection()
    posts = conn.execute('SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id ORDER BY p.id DESC').fetchall()
    conn.close()
    
    return render_template('community.html', posts=posts)

# 로그아웃
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # 0.0.0.0으로 설정해야 외부(AWS)에서도 접속 가능
    app.run(host='0.0.0.0', port=5000, debug=True)