from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import json
from datetime import datetime, date
import logging
import hashlib
import secrets
import os

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# 本番環境ではSECRET_KEYを環境変数から取得
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# 本番環境設定
if os.environ.get('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
else:
    app.config['DEBUG'] = True

class AISchoolTodoManager:
    def __init__(self):
        self.db_name = 'ai_school_todos.db'
        self.init_database()
        
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        with self.get_connection() as conn:
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
            
            # 既存テーブルの構造をチェックしてマイグレーション
            self.migrate_tables(cursor)
            
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
    
    def create_user(self, username, password):
        """新しいユーザーを作成"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                password_hash = self.hash_password(password)
                cursor.execute('''
                    INSERT INTO users (username, password_hash)
                    VALUES (?, ?)
                ''', (username, password_hash))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # ユーザー名が既に存在
    
    def authenticate_user(self, username, password):
        """ユーザー認証"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            password_hash = self.hash_password(password)
            logger.info(f"認証試行: ユーザー名={username}, ハッシュ={password_hash[:10]}...")
            
            cursor.execute('''
                SELECT id, username FROM users
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
    
    def insert_sample_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # デフォルトユーザーを作成
            cursor.execute('SELECT COUNT(*) FROM users')
            if cursor.fetchone()[0] == 0:
                default_user_id = self.create_user('demo', 'demo123')
                if default_user_id:
                    # 今日の日付
                    today = date.today().isoformat()
                    
                    # サンプルの定常タスク
                    sample_routines = [
                        ('r1', default_user_id, '歯磨き', 0),
                        ('r2', default_user_id, '朝食を食べる', 1),
                        ('r3', default_user_id, '軽いストレッチ', 2)
                    ]
                    
                    cursor.executemany('''
                        INSERT INTO routine_tasks (id, user_id, text, position)
                        VALUES (?, ?, ?, ?)
                    ''', sample_routines)
                    
                    # サンプルの日次タスク
                    sample_tasks = [
                        ('task_1', default_user_id, 'AI入門コース セクション1完了', 0, today, 0, 0),
                        ('task_2', default_user_id, '動画視聴 (チャプター2)', 0, today, 1, 1),
                        ('task_3', default_user_id, '演習問題1-Aを解く', 0, today, 1, 2),
                        ('task_4', default_user_id, 'AI倫理に関する記事を読む', 0, today, 0, 3),
                        ('task_5', default_user_id, 'メンターに質問リストを送る', 0, today, 0, 4),
                    ]
                    
                    cursor.executemany('''
                        INSERT INTO daily_tasks (id, user_id, text, completed, date, indent, position)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', sample_tasks)
                    
                    conn.commit()
    
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
            cursor.execute('DELETE FROM routine_completions WHERE routine_id = ?', (task_id,))
            conn.commit()
        
    def get_daily_tasks(self, user_id, date_str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM daily_tasks
                WHERE user_id = ? AND date = ?
                ORDER BY position, created_at
            ''', (user_id, date_str,))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_daily_task(self, user_id, task_id, text, date_str, indent=0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 最大ポジションを取得
            cursor.execute('SELECT MAX(position) FROM daily_tasks WHERE user_id = ? AND date = ?', (user_id, date_str))
            max_pos = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                INSERT INTO daily_tasks (id, user_id, text, completed, date, indent, position)
                VALUES (?, ?, ?, 0, ?, ?, ?)
            ''', (task_id, user_id, text, date_str, indent, max_pos + 1))
            
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
            
            for position, task_id in enumerate(task_ids):
                cursor.execute('''
                    UPDATE daily_tasks
                    SET position = ?
                    WHERE id = ? AND date = ?
                ''', (position, task_id, date_str))
            
            conn.commit()
    
    def get_routine_completion(self, user_id, routine_id, date_str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT rc.completed FROM routine_completions rc
                JOIN routine_tasks rt ON rt.id = rc.routine_id
                WHERE rc.routine_id = ? AND rc.date = ? AND rt.user_id = ?
            ''', (routine_id, date_str, user_id))
            
            result = cursor.fetchone()
            return result[0] if result else False
    
    def set_routine_completion(self, user_id, routine_id, date_str, completed):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # まずroutine_taskが該当ユーザーのものかチェック
            cursor.execute('SELECT id FROM routine_tasks WHERE id = ? AND user_id = ?', (routine_id, user_id))
            if cursor.fetchone():
                cursor.execute('''
                    INSERT OR REPLACE INTO routine_completions (routine_id, date, completed)
                    VALUES (?, ?, ?)
                ''', (routine_id, date_str, completed))
                conn.commit()

# アプリケーションインスタンス
todo_manager = AISchoolTodoManager()

def login_required(f):
    """ログインが必要なルートのデコレータ"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = todo_manager.authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
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
@login_required
def index():
    return render_template('ai_school_todo.html')

@app.route('/api/tasks/<date_str>')
@login_required
def get_tasks(date_str):
    try:
        user_id = session['user_id']
        daily_tasks = todo_manager.get_daily_tasks(user_id, date_str)
        routine_tasks = todo_manager.get_routine_tasks(user_id)
        
        # 定常タスクの完了状態を取得
        for task in routine_tasks:
            task['completed'] = todo_manager.get_routine_completion(user_id, task['id'], date_str)
        
        return jsonify({
            'daily_tasks': daily_tasks,
            'routine_tasks': routine_tasks
        })
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['POST'])
@login_required
def add_task():
    try:
        data = request.get_json()
        user_id = session['user_id']
        todo_manager.add_daily_task(
            user_id,
            data['id'],
            data['text'],
            data['date'],
            data.get('indent', 0)
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    try:
        data = request.get_json()
        todo_manager.update_daily_task(
            task_id,
            text=data.get('text'),
            completed=data.get('completed'),
            indent=data.get('indent')
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    try:
        todo_manager.delete_daily_task(task_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/toggle', methods=['POST'])
@login_required
def toggle_routine():
    try:
        data = request.get_json()
        user_id = session['user_id']
        current_state = todo_manager.get_routine_completion(user_id, data['routine_id'], data['date'])
        new_state = not current_state
        todo_manager.set_routine_completion(user_id, data['routine_id'], data['date'], new_state)
        return jsonify({'success': True, 'completed': new_state})
    except Exception as e:
        logger.error(f"Error toggling routine: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reorder', methods=['POST'])
@login_required
def reorder_tasks():
    try:
        data = request.get_json()
        todo_manager.reorder_daily_tasks(data['task_ids'], data['date'])
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error reordering tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine', methods=['POST'])
@login_required
def add_routine_task():
    try:
        data = request.get_json()
        user_id = session['user_id']
        indent = data.get('indent', 0)  # indentが指定されていない場合は0
        todo_manager.add_routine_task(user_id, data['id'], data['text'], indent)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding routine task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routine/<task_id>', methods=['PUT'])
@login_required
def update_routine_task(task_id):
    try:
        data = request.get_json()
        todo_manager.update_routine_task(
            task_id,
            text=data.get('text'),
            indent=data.get('indent')
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating routine task: {e}")
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5004)