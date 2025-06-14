from flask import Flask, jsonify, request, session, redirect, url_for
import sqlite3
import hashlib
import secrets
import os
import logging
from functools import wraps

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# セッション設定
if os.environ.get('VERCEL'):
    app.secret_key = 'suna-todo-fixed-secret-key-for-vercel-2024'
else:
    app.secret_key = secrets.token_hex(16)

# データベース設定
def get_db_path():
    if os.environ.get('VERCEL'):
        return '/tmp/suna_todo.db'
    else:
        return 'suna_todo.db'

def init_database():
    """データベースを初期化"""
    db_path = get_db_path()
    logger.info(f"Initializing database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ユーザーテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # タスクテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # デモユーザーを作成
        password_hash = hashlib.sha256('demo123'.encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash)
            VALUES (?, ?)
        ''', ('demo', password_hash))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def authenticate_user(username, password):
    """ユーザー認証"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            SELECT id, username FROM users
            WHERE username = ? AND password_hash = ?
        ''', (username, password_hash))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'id': result[0], 'username': result[1]}
        return None
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ルート定義
@app.route('/')
def index():
    try:
        # データベース初期化
        init_database()
        
        if 'user_id' not in session:
            return '''
            <html>
            <body>
                <h1>TODO App - ログイン</h1>
                <form method="post" action="/login">
                    <p>ユーザー名: <input type="text" name="username" value="demo" required></p>
                    <p>パスワード: <input type="password" name="password" value="demo123" required></p>
                    <p><input type="submit" value="ログイン"></p>
                </form>
                <p>デモアカウント: demo / demo123</p>
            </body>
            </html>
            '''
        else:
            return f'''
            <html>
            <body>
                <h1>TODO App - ようこそ {session.get("username")} さん</h1>
                <p><a href="/logout">ログアウト</a></p>
                <p><a href="/api/test">API テスト</a></p>
                <p>TODOアプリが正常に動作しています！</p>
            </body>
            </html>
            '''
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f'Error: {str(e)}', 500

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form['username']
        password = request.form['password']
        
        user = authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return '''
            <html>
            <body>
                <h1>ログイン失敗</h1>
                <p>ユーザー名またはパスワードが間違っています</p>
                <p><a href="/">戻る</a></p>
            </body>
            </html>
            '''
    except Exception as e:
        logger.error(f"Login error: {e}")
        return f'Login error: {str(e)}', 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/test')
@login_required
def api_test():
    return jsonify({
        'status': 'success',
        'message': 'API is working!',
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })

@app.route('/test')
def test():
    return 'Simple TODO App is working! 🎉'

@app.route('/health')
def health():
    try:
        # データベース接続テスト
        conn = sqlite3.connect(get_db_path())
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)