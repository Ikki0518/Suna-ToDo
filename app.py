from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import sqlite3
import hashlib
import secrets
import os
import logging
from functools import wraps
from datetime import datetime, date

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')

# セッション設定
if os.environ.get('VERCEL'):
    app.secret_key = 'suna-todo-fixed-secret-key-for-vercel-2024'
else:
    app.secret_key = secrets.token_hex(16)

# データベース設定
def get_db_path():
    if os.environ.get('VERCEL'):
        # Vercel環境では複数の場所を試してデータベースの永続化を改善
        possible_paths = [
            '/tmp/persistent_suna_todo.db',
            '/tmp/suna_todo.db'
        ]
        # 既存のデータベースがあるかチェック
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Using existing database: {path}")
                return path
        # なければ最初のパスを使用
        logger.info(f"Creating new database: {possible_paths[0]}")
        return possible_paths[0]
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
        
        # 日次タスクテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                date TEXT NOT NULL,
                indent INTEGER DEFAULT 0,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 定常タスクテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routine_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                indent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 既存のroutine_tasksテーブルにindentカラムを追加（存在しない場合）
        try:
            cursor.execute('ALTER TABLE routine_tasks ADD COLUMN indent INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            # カラムが既に存在する場合はエラーを無視
            pass
        
        # 定常タスク完了記録テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routine_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                routine_id TEXT NOT NULL,
                date TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                UNIQUE(user_id, routine_id, date),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # デモユーザーを作成
        password_hash = hashlib.sha256('demo123'.encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash)
            VALUES (?, ?)
        ''', ('demo', password_hash))
        
        # 管理者ユーザーを作成
        admin_password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash)
            VALUES (?, ?)
        ''', ('admin', admin_password_hash))
        logger.info("管理者ユーザー作成: admin/admin123")
        
        # サンプルタスクを作成（デモ用）
        today = datetime.now().strftime('%Y-%m-%d')
        
        # デモユーザーのIDを取得
        cursor.execute('SELECT id FROM users WHERE username = ?', ('demo',))
        demo_user = cursor.fetchone()
        if demo_user:
            demo_user_id = demo_user[0]
            
            # サンプル日次タスクを追加
            sample_daily_tasks = [
                'プログラミング学習を始める',
                'TODOアプリの使い方を覚える',
                'タスクを完了してみる'
            ]
            
            for i, task_text in enumerate(sample_daily_tasks):
                task_id = f'demo_daily_{i}_{today}'
                cursor.execute('''
                    INSERT OR IGNORE INTO daily_tasks (id, user_id, text, date, position, indent)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, demo_user_id, task_text, today, i, 0))
            
            # サンプル定常タスクを追加
            sample_routine_tasks = [
                '朝の学習タイム (30分)',
                '進捗の確認',
                '今日の振り返り'
            ]
            
            for i, task_text in enumerate(sample_routine_tasks):
                task_id = f'demo_routine_{i}'
                cursor.execute('''
                    INSERT OR IGNORE INTO routine_tasks (id, user_id, text, position)
                    VALUES (?, ?, ?, ?)
                ''', (task_id, demo_user_id, task_text, i))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully with sample data")
        
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

def create_user(username, password):
    """新規ユーザーを作成"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # ユーザー名の重複チェック
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return None  # ユーザー名が既に存在
        
        # パスワードをハッシュ化
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # 新規ユーザーを挿入
        cursor.execute('''
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
        ''', (username, password_hash))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"新規ユーザー作成: {username}")
        return user_id
        
    except Exception as e:
        logger.error(f"User creation error: {e}")
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
            return redirect(url_for('login'))
        else:
            return render_template('ai_school_todo.html', username=session.get('username'))
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return f'Error: {str(e)}', 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            user = authenticate_user(username, password)
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error='ユーザー名またはパスワードが間違っています')
        
        return render_template('login.html')
    except Exception as e:
        logger.error(f"Login error: {e}")
        return f'Login error: {str(e)}', 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """新規登録ページ"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('register.html', error='パスワードが一致しません')
        
        if len(username) < 3 or len(password) < 6:
            return render_template('register.html', error='ユーザー名は3文字以上、パスワードは6文字以上で入力してください')
        
        user_id = create_user(username, password)
        if user_id:
            return render_template('register.html', success='アカウントが作成されました。ログインしてください。')
        else:
            return render_template('register.html', error='そのユーザー名は既に使用されています')
    
    return render_template('register.html')

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

# APIエンドポイント
@app.route('/api/tasks/<date_str>')
@login_required
def get_tasks_by_date(date_str):
    try:
        user_id = session['user_id']
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 日次タスクを取得
        cursor.execute('''
            SELECT * FROM daily_tasks
            WHERE user_id = ? AND date = ?
            ORDER BY position, created_at
        ''', (user_id, date_str))
        daily_tasks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
        # 定常タスクを取得
        cursor.execute('''
            SELECT * FROM routine_tasks
            WHERE user_id = ?
            ORDER BY position, created_at
        ''', (user_id,))
        routine_tasks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
        # 定常タスクの完了状況を取得
        for task in routine_tasks:
            cursor.execute('''
                SELECT completed FROM routine_completions
                WHERE user_id = ? AND routine_id = ? AND date = ?
            ''', (user_id, task['id'], date_str))
            result = cursor.fetchone()
            task['completed'] = result[0] if result else False
        
        conn.close()
        
        return jsonify({
            'daily_tasks': daily_tasks,
            'routine_tasks': routine_tasks
        })
    except Exception as e:
        logger.error(f"Error in get_tasks_by_date: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/data')
@login_required
def get_data():
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        user_id = session['user_id']
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 日次タスクを取得
        cursor.execute('''
            SELECT * FROM daily_tasks
            WHERE user_id = ? AND date = ?
            ORDER BY position, created_at
        ''', (user_id, date_str))
        daily_tasks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
        # 定常タスクを取得
        cursor.execute('''
            SELECT * FROM routine_tasks
            WHERE user_id = ?
            ORDER BY position, created_at
        ''', (user_id,))
        routine_tasks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
        # 定常タスクの完了状況を取得
        for task in routine_tasks:
            cursor.execute('''
                SELECT completed FROM routine_completions
                WHERE user_id = ? AND routine_id = ? AND date = ?
            ''', (user_id, task['id'], date_str))
            result = cursor.fetchone()
            task['completed'] = result[0] if result else False
        
        conn.close()
        
        return jsonify({
            'daily_tasks': daily_tasks,
            'routine_tasks': routine_tasks
        })
    except Exception as e:
        logger.error(f"Error in get_data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['POST'])
@login_required
def add_daily_task():
    try:
        data = request.get_json()
        user_id = session['user_id']
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 最大ポジションを取得
        cursor.execute('SELECT MAX(position) FROM daily_tasks WHERE user_id = ? AND date = ?',
                      (user_id, data['date']))
        max_pos = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            INSERT INTO daily_tasks (id, user_id, text, date, position, indent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['id'], user_id, data['text'], data['date'], max_pos + 1, data.get('indent', 0)))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_daily_task(task_id):
    try:
        data = request.get_json()
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        update_fields = []
        values = []
        
        if 'text' in data:
            update_fields.append('text = ?')
            values.append(data['text'])
        if 'completed' in data:
            update_fields.append('completed = ?')
            values.append(data['completed'])
        if 'indent' in data:
            update_fields.append('indent = ?')
            values.append(data['indent'])
            
        if update_fields:
            values.append(task_id)
            cursor.execute(f'''
                UPDATE daily_tasks
                SET {', '.join(update_fields)}
                WHERE id = ?
            ''', values)
            
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_daily_task(task_id):
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('DELETE FROM daily_tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/toggle', methods=['POST'])
@login_required
def update_routine_completion():
    try:
        data = request.get_json()
        user_id = session['user_id']
        routine_id = data['routine_id']
        date_str = data['date']
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 現在の状態を取得
        cursor.execute('''
            SELECT completed FROM routine_completions
            WHERE user_id = ? AND routine_id = ? AND date = ?
        ''', (user_id, routine_id, date_str))
        result = cursor.fetchone()
        current_completed = result[0] if result else False
        
        # 状態を切り替え
        new_completed = not current_completed
        
        cursor.execute('''
            INSERT OR REPLACE INTO routine_completions (user_id, routine_id, date, completed)
            VALUES (?, ?, ?, ?)
        ''', (user_id, routine_id, date_str, new_completed))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'completed': new_completed})
    except Exception as e:
        logger.error(f"Error updating routine completion: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine', methods=['POST'])
@login_required
def add_routine_task():
    try:
        data = request.get_json()
        user_id = session['user_id']
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 最大ポジションを取得
        cursor.execute('SELECT MAX(position) FROM routine_tasks WHERE user_id = ?', (user_id,))
        max_pos = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            INSERT INTO routine_tasks (id, user_id, text, position, indent)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['id'], user_id, data['text'], max_pos + 1, data.get('indent', 0)))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/<task_id>', methods=['PUT'])
@login_required
def update_routine_task(task_id):
    try:
        data = request.get_json()
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        update_fields = []
        values = []
        
        if 'text' in data:
            update_fields.append('text = ?')
            values.append(data['text'])
        if 'indent' in data:
            update_fields.append('indent = ?')
            values.append(data['indent'])
            
        if update_fields:
            values.append(task_id)
            cursor.execute(f'''
                UPDATE routine_tasks
                SET {', '.join(update_fields)}
                WHERE id = ?
            ''', values)
            
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/<task_id>', methods=['DELETE'])
@login_required
def delete_routine_task(task_id):
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('DELETE FROM routine_tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    try:
        # データベース接続テスト
        conn = sqlite3.connect(get_db_path())
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# 管理者ダッシュボード
@app.route('/admin')
@login_required
def admin_dashboard():
    if session.get('username') != 'admin':
        return redirect(url_for('index'))
    
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 統計情報を取得
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM routine_tasks')
        task_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT username, created_at FROM users ORDER BY created_at DESC')
        users = cursor.fetchall()
        
        cursor.execute('''
            SELECT rt.text, rt.created_at, u.username
            FROM routine_tasks rt
            JOIN users u ON rt.user_id = u.id
            ORDER BY rt.created_at DESC
            LIMIT 10
        ''')
        recent_tasks = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin_dashboard.html',
                             user_count=user_count,
                             task_count=task_count,
                             users=users,
                             recent_tasks=recent_tasks)
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        return "管理者ダッシュボードでエラーが発生しました", 500

@app.route('/admin/users')
@login_required
def admin_users():
    if session.get('username') != 'admin':
        return redirect(url_for('index'))
    
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, created_at FROM users ORDER BY created_at DESC')
        users = cursor.fetchall()
        conn.close()
        
        return render_template('admin_users.html', users=users)
    except Exception as e:
        logger.error(f"Admin users error: {e}")
        return "ユーザー管理でエラーが発生しました", 500

@app.route('/admin/tasks')
@login_required
def admin_tasks():
    if session.get('username') != 'admin':
        return redirect(url_for('index'))
    
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('''
            SELECT rt.id, rt.text, 0 as completed, rt.created_at, u.username
            FROM routine_tasks rt
            JOIN users u ON rt.user_id = u.id
            ORDER BY rt.created_at DESC
        ''')
        tasks = cursor.fetchall()
        conn.close()
        
        return render_template('admin_tasks.html', tasks=tasks)
    except Exception as e:
        logger.error(f"Admin tasks error: {e}")
        return "タスク管理でエラーが発生しました", 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)