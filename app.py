from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import json
from datetime import datetime, date
import logging
import hashlib
import secrets
import os
from functools import wraps

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# テンプレート設定（app.pyから直接templatesフォルダを参照）
app = Flask(__name__, template_folder='templates', static_folder='static')

# 本番環境ではSECRET_KEYを環境変数から取得
# Vercel環境では固定キーを使用してセッション一貫性を確保
if os.environ.get('VERCEL'):
    app.secret_key = os.environ.get('SECRET_KEY', 'suna-todo-fixed-secret-key-for-vercel-2024')
else:
    app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# セッション設定（Vercel対応）
app.config['SESSION_COOKIE_HTTPONLY'] = True  # XSS防止
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF防止
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1時間
app.config['SESSION_COOKIE_NAME'] = 'suna_session'  # セッション名を明示的に設定

# 本番環境設定
if os.environ.get('VERCEL'):
    # Vercel環境での特別設定
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    app.config['SESSION_COOKIE_SECURE'] = False  # 一時的にfalseでテスト
    app.config['SESSION_COOKIE_DOMAIN'] = None  # ドメイン制限を解除
    logger.info("Running on Vercel - session cookie settings adjusted for serverless")
elif os.environ.get('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS必須
else:
    app.config['DEBUG'] = True
    app.config['SESSION_COOKIE_SECURE'] = False

# グローバルデータベース接続とマネージャー
_global_db_conn = None
_global_todo_manager = None

class AISchoolTodoManager:
    def __init__(self):
        # Vercel serverless環境でのデータベース設定
        import os
        
        # 環境変数からデータベースパスを取得、デフォルトは/tmp/suna_todo.db
        if os.environ.get('VERCEL'):
            # Vercel環境では/tmpディレクトリを使用
            self.db_name = '/tmp/suna_todo.db'
            # データベースファイルの永続化のために既存チェック
            if not os.path.exists(self.db_name):
                logger.info("Database file not found in /tmp, creating new one")
        else:
            # ローカル環境では相対パス
            self.db_name = 'suna_todo.db'
        
        logger.info(f"Database path: {self.db_name}")
        
        # データベースの初期化を確実に実行
        self._ensure_database()
        
    def _ensure_database(self):
        """データベースが初期化されていることを確認し、Vercel環境でのデータ永続化を改善"""
        global _global_db_conn
        
        logger.info(f"Ensuring database: {self.db_name}")
        
        # 既存の接続をクリーンアップ
        try:
            if _global_db_conn:
                _global_db_conn.close()
        except:
            pass
            
        # 新しい接続を作成
        _global_db_conn = sqlite3.connect(self.db_name, check_same_thread=False)
        _global_db_conn.row_factory = sqlite3.Row
        
        # WALモードを有効化（Vercel環境での安定性向上）
        try:
            _global_db_conn.execute('PRAGMA journal_mode=WAL')
            _global_db_conn.execute('PRAGMA synchronous=NORMAL')
            _global_db_conn.execute('PRAGMA cache_size=1000')
            _global_db_conn.execute('PRAGMA temp_store=memory')
        except:
            pass
        
        # テーブルの存在を確認
        cursor = _global_db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        
        if not cursor.fetchone():
            logger.info("Tables not found, initializing database")
            self.init_database()
        else:
            logger.info("Database tables exist, checking data consistency")
            # 管理者アカウントの存在を確認
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
            admin_count = cursor.fetchone()[0]
            if admin_count == 0:
                logger.info("No admin users found, creating admin accounts")
                self._create_essential_users()
            
            # ユーザー数をログ
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = "student"')
            student_users = cursor.fetchone()[0]
            logger.info(f"Database status - Total users: {total_users}, Students: {student_users}, Admins: {admin_count}")
        
    def get_connection(self):
        global _global_db_conn
        if _global_db_conn is None:
            self._ensure_database()
        return _global_db_conn
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ユーザーテーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'student',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 既存テーブルの構造をチェックしてマイグレーション
            self.migrate_tables(cursor)
            
            # 必須ユーザーを作成
            self._create_essential_users()
            
            conn.commit()
    
    def migrate_tables(self, cursor):
        """既存のテーブル構造をチェックし、必要に応じて更新"""
        # 既存のテーブルが存在するかチェック
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_tasks'")
        if cursor.fetchone():
            # user_idカラムが存在するかチェック
            cursor.execute("PRAGMA table_info(daily_tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'user_id' not in columns:
                # 既存のテーブルをバックアップして新しい構造で作り直し
                cursor.execute('DROP TABLE IF EXISTS daily_tasks')
                cursor.execute('DROP TABLE IF EXISTS routine_tasks')
                cursor.execute('DROP TABLE IF EXISTS routine_completions')
        
        # 新しい構造でテーブルを作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                text TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                date TEXT NOT NULL,
                indent INTEGER DEFAULT 0,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routine_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                text TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routine_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                routine_id TEXT NOT NULL,
                date TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                UNIQUE(user_id, routine_id, date),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
            
        # サンプルデータを挿入
        self.insert_sample_data()
    
    def hash_password(self, password):
        """パスワードをハッシュ化"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username, password, role='student'):
        """新しいユーザーを作成"""
        try:
            # データベース接続を確実に取得
            self._ensure_database()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                password_hash = self.hash_password(password)
                cursor.execute('''
                    INSERT INTO users (username, password_hash, role)
                    VALUES (?, ?, ?)
                ''', (username, password_hash, role))
                conn.commit()
                user_id = cursor.lastrowid
                logger.info(f"User created successfully: {username} (ID: {user_id}, Role: {role})")
                
                return user_id
        except sqlite3.IntegrityError as e:
            logger.warning(f"User creation failed - username already exists: {username}")
            return None  # ユーザー名が既に存在
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}", exc_info=True)
            return None
    
    def authenticate_user(self, username, password):
        """ユーザー認証"""
        # データベース接続を確実に取得
        self._ensure_database()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            password_hash = self.hash_password(password)
            
            cursor.execute('''
                SELECT id, username, role FROM users
                WHERE username = ? AND password_hash = ?
            ''', (username, password_hash))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"認証成功: ユーザーID={result[0]}")
            else:
                logger.warning(f"認証失敗: ユーザー名={username}")
            
            return dict(result) if result else None
    
    def _create_essential_users(self):
        """必須ユーザー（管理者アカウント）を作成"""
        try:
            # 既存の管理者数を確認
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
                admin_count = cursor.fetchone()[0]
                
                if admin_count > 0:
                    logger.info(f"Admin accounts already exist: {admin_count}")
                    return
            
            # デモアカウントを作成
            demo_id = self.create_user('demo', 'demo123', 'student')
            if demo_id:
                logger.info("Demo user created successfully")
                
        except Exception as e:
            logger.error(f"Error creating essential users: {e}", exc_info=True)

    def insert_sample_data(self):
        """サンプルデータは作成せず、実際の登録ユーザーのみを使用"""
        logger.info("Database initialized without sample data - only real registered users will be shown")
    
    def get_routine_tasks(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM routine_tasks
                WHERE user_id = ?
                ORDER BY position, created_at
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        
    def add_routine_task(self, user_id, task_id, text, indent=0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 最大ポジションを取得
            cursor.execute('SELECT MAX(position) FROM routine_tasks WHERE user_id = ?', (user_id,))
            max_pos = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                INSERT INTO routine_tasks (id, user_id, text, position, indent)
                VALUES (?, ?, ?, ?, ?)
            ''', (task_id, user_id, text, max_pos + 1, indent))
            
            conn.commit()
    
    def update_routine_task(self, task_id, text=None, indent=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            update_fields = []
            values = []
            
            if text is not None:
                update_fields.append('text = ?')
                values.append(text)
            if indent is not None:
                update_fields.append('indent = ?')
                values.append(indent)
                
            if update_fields:
                values.append(task_id)
                cursor.execute(f'''
                    UPDATE routine_tasks 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', values)
                conn.commit()
    
    def delete_routine_task(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM routine_tasks WHERE id = ?', (task_id,))
            conn.commit()
    
    def get_routine_completion(self, user_id, routine_id, date_str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT completed FROM routine_completions
                WHERE user_id = ? AND routine_id = ? AND date = ?
            ''', (user_id, routine_id, date_str))
            result = cursor.fetchone()
            return result[0] if result else False
    
    def set_routine_completion(self, user_id, routine_id, date_str, completed):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO routine_completions (user_id, routine_id, date, completed)
                VALUES (?, ?, ?, ?)
            ''', (user_id, routine_id, date_str, completed))
            conn.commit()
    
    def get_daily_tasks(self, user_id, date_str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM daily_tasks
                WHERE user_id = ? AND date = ?
                ORDER BY position, created_at
            ''', (user_id, date_str))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_daily_task(self, user_id, task_id, text, date_str, indent=0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 最大ポジションを取得
            cursor.execute('SELECT MAX(position) FROM daily_tasks WHERE user_id = ? AND date = ?', (user_id, date_str))
            max_pos = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                INSERT INTO daily_tasks (id, user_id, text, date, position, indent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, user_id, text, date_str, max_pos + 1, indent))
            
            conn.commit()
    
    def update_daily_task(self, task_id, text=None, completed=None, indent=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            update_fields = []
            values = []
            
            if text is not None:
                update_fields.append('text = ?')
                values.append(text)
            if completed is not None:
                update_fields.append('completed = ?')
                values.append(completed)
            if indent is not None:
                update_fields.append('indent = ?')
                values.append(indent)
                
            if update_fields:
                values.append(task_id)
                cursor.execute(f'''
                    UPDATE daily_tasks 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', values)
                conn.commit()
    
    def delete_daily_task(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM daily_tasks WHERE id = ?', (task_id,))
            conn.commit()
    
    def reorder_daily_tasks(self, task_ids, date_str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for i, task_id in enumerate(task_ids):
                cursor.execute('''
                    UPDATE daily_tasks 
                    SET position = ?
                    WHERE id = ? AND date = ?
                ''', (i, task_id, date_str))
            conn.commit()

# TODOマネージャーのインスタンス化
def get_todo_manager():
    """TODOマネージャーのシングルトンインスタンスを取得"""
    global _global_todo_manager
    if _global_todo_manager is None:
        _global_todo_manager = AISchoolTodoManager()
    return _global_todo_manager

# ログイン必須デコレータ
def login_required(f):
    """ログインが必要なルートのデコレータ"""
    @wraps(f)
    def login_decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return login_decorated_function

# ルート定義
@app.route('/test')
def test():
    return 'Complete TODO App test route is working! 🎉'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        todo_manager = get_todo_manager()
        user = todo_manager.authenticate_user(username, password)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            logger.info(f"User logged in successfully: {username} (Role: {user['role']})")
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        todo_manager = get_todo_manager()
        user_id = todo_manager.create_user(username, password, role='student')
        
        if user_id:
            logger.info(f"New user registered: {username}")
            return redirect(url_for('login'))
        else:
            return render_template('register.html', error='Username already exists')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    # ログインチェック
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('ai_school_todo.html', username=session.get('username'))

# データ取得API
@app.route('/api/data')
@login_required
def get_data():
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        user_id = session['user_id']
        
        todo_manager = get_todo_manager()
        
        # 日次タスクと定常タスクを取得
        daily_tasks = todo_manager.get_daily_tasks(user_id, date_str)
        routine_tasks = todo_manager.get_routine_tasks(user_id)
        
        # 定常タスクの完了状況を取得
        for task in routine_tasks:
            task['completed'] = todo_manager.get_routine_completion(user_id, task['id'], date_str)
        
        return jsonify({
            'daily_tasks': daily_tasks,
            'routine_tasks': routine_tasks
        })
    except Exception as e:
        logger.error(f"Error in get_data: {e}")
        return jsonify({'error': str(e)}), 500

# 日次タスクAPI
@app.route('/api/daily_task', methods=['POST'])
@login_required
def add_daily_task():
    try:
        data = request.get_json()
        todo_manager = get_todo_manager()
        todo_manager.add_daily_task(
            session['user_id'], 
            data['id'], 
            data['text'], 
            data['date'], 
            data.get('indent', 0)
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/daily_task/<task_id>', methods=['PUT'])
@login_required
def update_daily_task(task_id):
    try:
        data = request.get_json()
        todo_manager = get_todo_manager()
        todo_manager.update_daily_task(
            task_id, 
            data.get('text'), 
            data.get('completed'), 
            data.get('indent')
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/daily_task/<task_id>', methods=['DELETE'])
@login_required
def delete_daily_task(task_id):
    try:
        todo_manager = get_todo_manager()
        todo_manager.delete_daily_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting daily task: {e}")
        return jsonify({'error': str(e)}), 500

# 定常タスク完了状況API
@app.route('/api/routine_completion', methods=['POST'])
@login_required
def update_routine_completion():
    try:
        data = request.get_json()
        todo_manager = get_todo_manager()
        todo_manager.set_routine_completion(
            session['user_id'], 
            data['routine_id'], 
            data['date'], 
            data['completed']
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating routine completion: {e}")
        return jsonify({'error': str(e)}), 500

# タスク並び替えAPI
@app.route('/api/reorder_daily_tasks', methods=['POST'])
@login_required
def reorder_daily_tasks():
    try:
        data = request.get_json()
        todo_manager = get_todo_manager()
        todo_manager.reorder_daily_tasks(data['task_ids'], data['date'])
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error reordering daily tasks: {e}")
        return jsonify({'error': str(e)}), 500

# 定常タスクAPI
@app.route('/api/routine_task', methods=['POST'])
@login_required
def add_routine_task():
    try:
        data = request.get_json()
        todo_manager = get_todo_manager()
        todo_manager.add_routine_task(
            session['user_id'], 
            data['id'], 
            data['text'], 
            data.get('indent', 0)
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine_task/<task_id>', methods=['PUT'])
@login_required
def update_routine_task(task_id):
    try:
        data = request.get_json()
        todo_manager = get_todo_manager()
        todo_manager.update_routine_task(
            task_id, 
            data.get('text'), 
            data.get('indent')
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/<task_id>', methods=['DELETE'])
@login_required
def delete_routine_task(task_id):
    try:
        todo_manager = get_todo_manager()
        todo_manager.delete_routine_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting routine task: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)