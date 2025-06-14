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

# Vercel環境でのパス設定
current_dir = os.path.dirname(__file__)
template_path = os.path.join(current_dir, '..', 'templates')
static_path = os.path.join(current_dir, '..', 'static')

app = Flask(__name__,
           template_folder=template_path,
           static_folder=static_path if os.path.exists(static_path) else None)
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
                
                # ユーザー作成後の統計をログ
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM users WHERE role = "student"')
                student_users = cursor.fetchone()[0]
                logger.info(f"Database updated - Total users: {total_users}, Students: {student_users}")
                
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
            logger.info(f"認証試行: ユーザー名={username}, ハッシュ={password_hash[:10]}...")
            
            cursor.execute('''
                SELECT id, username, role FROM users
                WHERE username = ? AND password_hash = ?
            ''', (username, password_hash))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"認証成功: ユーザーID={result[0]}")
            else:
                logger.warning(f"認証失敗: ユーザー名={username}")
                # デバッグ用：該当ユーザーの存在確認
                cursor.execute('SELECT username, password_hash FROM users WHERE username = ?', (username,))
                user_check = cursor.fetchone()
                if user_check:
                    logger.warning(f"ユーザーは存在するがパスワードが不一致: 保存ハッシュ={user_check[1][:10]}...")
                else:
                    logger.warning(f"ユーザーが見つかりません: {username}")
            
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
            
            # 管理者アカウントのみを作成（受講者は新規登録で作成）
            admin1_id = self.create_user('ikki_y0518@icloud.com', 'ikki0518', 'admin')
            if admin1_id:
                logger.info("Admin user (ikki_y0518@icloud.com) created successfully")
                
            admin2_id = self.create_user('admin', 'admin123', 'admin')
            if admin2_id:
                logger.info("Admin user (admin) created successfully")
            
            # デモアカウントも作成（表示されていたため）
            demo_id = self.create_user('demo', 'demo123', 'admin')
            if demo_id:
                logger.info("Demo admin user (demo) created successfully")
                
        except Exception as e:
            logger.error(f"Error creating essential users: {e}", exc_info=True)

    def insert_sample_data(self):
        """サンプルデータは作成せず、実際の登録ユーザーのみを使用"""
        logger.info("Database initialized without sample data - only real registered users will be shown")
        # サンプルデータは作成しない
    
    def get_all_users(self):
        """すべてのユーザーを取得（管理者用）"""
        # データベース接続を確実に取得
        self._ensure_database()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, role, created_at 
                FROM users 
                WHERE role = 'student'
                ORDER BY created_at DESC
            ''')
            users = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Retrieved {len(users)} student users for admin dashboard")
            return users
    
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
    
    def get_user_progress(self, user_id, date_str):
        """指定ユーザーの指定日の進捗を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 本日のTODOタスク進捗
            cursor.execute('''
                SELECT COUNT(*) as total_tasks,
                       COUNT(CASE WHEN completed = 1 THEN 1 END) as completed_tasks
                FROM daily_tasks
                WHERE user_id = ? AND date = ?
            ''', (user_id, date_str))
            daily_progress = cursor.fetchone()
            
            # 定常TODOタスク進捗
            cursor.execute('''
                SELECT COUNT(*) as total_routines
                FROM routine_tasks
                WHERE user_id = ?
            ''', (user_id,))
            routine_total = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) as completed_routines
                FROM routine_completions
                WHERE user_id = ? AND date = ? AND completed = 1
            ''', (user_id, date_str))
            routine_completed = cursor.fetchone()[0]
            
            total_tasks = daily_progress[0] + routine_total
            completed_tasks = daily_progress[1] + routine_completed
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            return {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round(completion_rate, 1),
                'daily_tasks': {
                    'total': daily_progress[0],
                    'completed': daily_progress[1]
                },
                'routine_tasks': {
                    'total': routine_total,
                    'completed': routine_completed
                }
            }

def get_todo_manager():
    """グローバルなTODOマネージャーを取得"""
    global _global_todo_manager
    if _global_todo_manager is None:
        _global_todo_manager = AISchoolTodoManager()
    return _global_todo_manager

# グローバルインスタンス
todo_manager = get_todo_manager()

def login_required(f):
    """ログインが必要なルートのデコレータ"""
    from functools import wraps
    @wraps(f)
    def login_decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return login_decorated_function

def admin_required(f):
    """管理者権限が必要なルートのデコレータ"""
    from functools import wraps
    @wraps(f)
    def admin_decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)
    return admin_decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = todo_manager.authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_role'] = user['role']
            logger.info(f"User logged in: {user['username']}, role: {user['role']}")
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='ユーザー名またはパスワードが間違っています')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('register.html', error='パスワードが一致しません')
        
        if len(username) < 3 or len(password) < 6:
            return render_template('register.html', error='ユーザー名は3文字以上、パスワードは6文字以上で入力してください')
        
        user_id = todo_manager.create_user(username, password)
        if user_id:
            return render_template('register.html', success='アカウントが作成されました。ログインしてください。')
        else:
            return render_template('register.html', error='そのユーザー名は既に使用されています')
    
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

# デバッグ用のテストルート
@app.route('/test')
def test():
    return 'API New TODO App is working! 🎉'

@app.route('/api/data')
@login_required
def get_data():
    try:
        user_id = session['user_id']
        date_str = request.args.get('date', date.today().isoformat())
        
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
        logger.error(f"Error getting data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/daily_task', methods=['POST'])
@login_required
def add_daily_task():
    try:
        data = request.json
        user_id = session['user_id']
        indent = data.get('indent', 0)
        
        todo_manager.add_daily_task(
            user_id, data['id'], data['text'], data['date'], indent
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/daily_task/<task_id>', methods=['PUT'])
@login_required
def update_daily_task(task_id):
    try:
        data = request.json
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
        todo_manager.delete_daily_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting daily task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine_completion', methods=['POST'])
@login_required
def update_routine_completion():
    try:
        data = request.json
        user_id = session['user_id']
        current_state = todo_manager.get_routine_completion(user_id, data['routine_id'], data['date'])
        new_state = not current_state
        todo_manager.set_routine_completion(user_id, data['routine_id'], data['date'], new_state)
        return jsonify({'success': True, 'completed': new_state})
    except Exception as e:
        logger.error(f"Error updating routine completion: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reorder_daily_tasks', methods=['POST'])
@login_required
def reorder_daily_tasks():
    try:
        data = request.json
        todo_manager.reorder_daily_tasks(data['task_ids'], data['date'])
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error reordering daily tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine_task', methods=['POST'])
@login_required
def add_routine_task():
    try:
        data = request.json
        user_id = session['user_id']
        indent = data.get('indent', 0)
        todo_manager.add_routine_task(user_id, data['id'], data['text'], indent)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine_task/<task_id>', methods=['PUT'])
@login_required
def update_routine_task(task_id):
    try:
        data = request.json
        todo_manager.update_routine_task(
            task_id, 
            data.get('text'),
            data.get('indent')
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin_dashboard():
    """管理者ダッシュボードのエントリーポイント"""
    return render_template('instructor_dashboard.html')

@app.route('/api/admin/stats')
@admin_required
def get_admin_stats():
    """管理者用統計情報API"""
    try:
        manager = get_todo_manager()
        
        # 基本統計の取得
        with manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 総受講生数（学生のみ）
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = "student"')
            total_students = cursor.fetchone()[0]
            
            # 今日のアクティブユーザー数の計算（今日タスクを持つユーザー数）
            today = date.today().isoformat()
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id) FROM (
                    SELECT user_id FROM daily_tasks WHERE date = ?
                    UNION
                    SELECT user_id FROM routine_completions WHERE date = ?
                )
            ''', (today, today))
            active_users_today = cursor.fetchone()[0]
            
            # 平均完了率の計算
            if total_students > 0:
                cursor.execute('''
                    SELECT AVG(completion_rate) FROM (
                        SELECT 
                            u.id,
                            CASE 
                                WHEN (daily_total + routine_total) > 0 THEN 
                                    CAST((daily_completed + routine_completed) AS FLOAT) / (daily_total + routine_total) * 100
                                ELSE 0
                            END as completion_rate
                        FROM users u
                        LEFT JOIN (
                            SELECT user_id, 
                                   COUNT(*) as daily_total,
                                   COUNT(CASE WHEN completed = 1 THEN 1 END) as daily_completed
                            FROM daily_tasks 
                            WHERE date = ?
                            GROUP BY user_id
                        ) dt ON u.id = dt.user_id
                        LEFT JOIN (
                            SELECT user_id,
                                   COUNT(*) as routine_total
                            FROM routine_tasks
                            GROUP BY user_id
                        ) rt ON u.id = rt.user_id
                        LEFT JOIN (
                            SELECT user_id,
                                   COUNT(CASE WHEN completed = 1 THEN 1 END) as routine_completed
                            FROM routine_completions
                            WHERE date = ?
                            GROUP BY user_id
                        ) rc ON u.id = rc.user_id
                        WHERE u.role = 'student'
                    )
                ''', (today, today))
                avg_completion_result = cursor.fetchone()[0]
                average_completion_rate = round(avg_completion_result or 0, 1)
            else:
                average_completion_rate = 0
        
        stats = {
            'total_students': total_students,
            'active_users_today': active_users_today,
            'average_completion_rate': average_completion_rate
        }
        
        logger.info(f"Admin stats: {stats}")
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Admin stats error: {e}", exc_info=True)
        return jsonify({'error': 'データの読み込みに失敗しました'}), 500

@app.route('/api/admin/users')
@admin_required
def get_admin_users():
    """管理者用受講者一覧API"""
    try:
        manager = get_todo_manager()
        users = manager.get_all_users()
        
        logger.info(f"Retrieved {len(users)} users for admin dashboard")
        
        # 各ユーザーの今日の進捗を追加
        today = date.today().isoformat()
        for user in users:
            try:
                progress = manager.get_user_progress(user['id'], today)
                user['today_progress'] = progress
            except Exception as e:
                logger.warning(f"Could not get progress for user {user['id']}: {e}")
                # エラー時はデフォルト値を設定
                user['today_progress'] = {
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'completion_rate': 0
                }
        
        logger.info("Successfully processed all users")
        return jsonify(users)
    except Exception as e:
        logger.error(f"Admin users error: {e}", exc_info=True)
        # エラー時は空のリストを返す（実際の登録ユーザーのみ表示）
        return jsonify([])

@app.route('/api/admin/users/<int:user_id>/progress')
@admin_required
def get_admin_user_progress(user_id):
    """管理者用特定受講者の進捗API"""
    try:
        manager = get_todo_manager()
        date_str = request.args.get('date', date.today().isoformat())
        progress = manager.get_user_progress(user_id, date_str)
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/<task_id>', methods=['DELETE'])
@login_required
def delete_routine_task(task_id):
    try:
        todo_manager.delete_routine_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting routine task: {e}")
        return jsonify({'error': str(e)}), 500

# Vercel用のhandler関数を定義
def handler(request, start_response):
    """Vercel用のWSGIハンドラー"""
    return app(request, start_response)

# Vercel用のアプリケーションオブジェクト
# Vercelは自動的にappオブジェクトまたはhandler関数を検出します
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5004)