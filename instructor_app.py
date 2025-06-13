from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime, date, timedelta
import json
import os
import secrets

app = Flask(__name__)
# 本番環境ではSECRET_KEYを環境変数から取得
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# 本番環境設定
if os.environ.get('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
else:
    app.config['DEBUG'] = True

class InstructorDashboard:
    def __init__(self):
        self.db_name = 'ai_school_todos.db'
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_all_users(self):
        """全ての受講者を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, created_at FROM users
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_progress(self, user_id, date_str=None):
        """特定の受講者の進捗を取得"""
        if date_str is None:
            date_str = date.today().isoformat()
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 日次タスクの進捗
            cursor.execute('''
                SELECT COUNT(*) as total, SUM(completed) as completed
                FROM daily_tasks
                WHERE user_id = ? AND date = ?
            ''', (user_id, date_str))
            daily_progress = dict(cursor.fetchone())
            
            # 定常タスクの進捗
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM routine_tasks
                WHERE user_id = ?
            ''', (user_id,))
            routine_total = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) as completed
                FROM routine_completions rc
                JOIN routine_tasks rt ON rt.id = rc.routine_id
                WHERE rt.user_id = ? AND rc.date = ? AND rc.completed = 1
            ''', (user_id, date_str))
            routine_completed = cursor.fetchone()[0]
            
            return {
                'daily': {
                    'total': daily_progress['total'] or 0,
                    'completed': daily_progress['completed'] or 0
                },
                'routine': {
                    'total': routine_total or 0,
                    'completed': routine_completed or 0
                }
            }
    
    def get_user_tasks(self, user_id, date_str=None):
        """特定の受講者のタスク詳細を取得"""
        if date_str is None:
            date_str = date.today().isoformat()
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 日次タスク
            cursor.execute('''
                SELECT id, text, completed, indent, position
                FROM daily_tasks
                WHERE user_id = ? AND date = ?
                ORDER BY position, created_at
            ''', (user_id, date_str))
            daily_tasks = [dict(row) for row in cursor.fetchall()]
            
            # 定常タスク
            cursor.execute('''
                SELECT rt.id, rt.text, rt.position,
                       COALESCE(rc.completed, 0) as completed
                FROM routine_tasks rt
                LEFT JOIN routine_completions rc ON rt.id = rc.routine_id AND rc.date = ?
                WHERE rt.user_id = ?
                ORDER BY rt.position, rt.created_at
            ''', (date_str, user_id))
            routine_tasks = [dict(row) for row in cursor.fetchall()]
            
            return {
                'daily_tasks': daily_tasks,
                'routine_tasks': routine_tasks
            }
    
    def get_weekly_progress(self, user_id):
        """過去7日間の進捗を取得"""
        today = date.today()
        weekly_data = []
        
        for i in range(7):
            target_date = today - timedelta(days=i)
            date_str = target_date.isoformat()
            progress = self.get_user_progress(user_id, date_str)
            
            daily_total = progress['daily']['total']
            daily_completed = progress['daily']['completed']
            routine_total = progress['routine']['total']
            routine_completed = progress['routine']['completed']
            
            total_tasks = daily_total + routine_total
            total_completed = daily_completed + routine_completed
            
            completion_rate = (total_completed / total_tasks * 100) if total_tasks > 0 else 0
            
            weekly_data.append({
                'date': date_str,
                'completion_rate': round(completion_rate, 1),
                'total_tasks': total_tasks,
                'completed_tasks': total_completed
            })
        
        return list(reversed(weekly_data))
    
    def get_overall_stats(self):
        """全体統計を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 総受講者数
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # 今日のアクティブユーザー数（今日タスクがあるユーザー）
            today = date.today().isoformat()
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id)
                FROM daily_tasks
                WHERE date = ?
            ''', (today,))
            active_today = cursor.fetchone()[0]
            
            # 平均完了率を計算（よりシンプルな方法で）
            cursor.execute('SELECT id FROM users')
            users = cursor.fetchall()
            
            total_completion_rates = []
            for user_row in users:
                user_id = user_row[0]
                progress = self.get_user_progress(user_id, today)
                
                daily_total = progress['daily']['total']
                daily_completed = progress['daily']['completed']
                routine_total = progress['routine']['total']
                routine_completed = progress['routine']['completed']
                
                total_tasks = daily_total + routine_total
                total_completed = daily_completed + routine_completed
                
                if total_tasks > 0:
                    completion_rate = (total_completed / total_tasks) * 100
                    total_completion_rates.append(completion_rate)
            
            avg_completion = sum(total_completion_rates) / len(total_completion_rates) if total_completion_rates else 0
            
            return {
                'total_users': total_users,
                'active_today': active_today,
                'avg_completion_rate': round(avg_completion, 1)
            }

# アプリケーションインスタンス
dashboard = InstructorDashboard()

@app.route('/')
def index():
    """講師ダッシュボードのメインページ"""
    return render_template('instructor_dashboard.html')

@app.route('/api/stats')
def get_stats():
    """全体統計を取得"""
    try:
        stats = dashboard.get_overall_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
def get_users():
    """全受講者一覧を取得"""
    try:
        users = dashboard.get_all_users()
        today = date.today().isoformat()
        
        # 各ユーザーの今日の進捗を追加
        for user in users:
            progress = dashboard.get_user_progress(user['id'], today)
            daily_total = progress['daily']['total']
            daily_completed = progress['daily']['completed']
            routine_total = progress['routine']['total']
            routine_completed = progress['routine']['completed']
            
            total_tasks = daily_total + routine_total
            total_completed = daily_completed + routine_completed
            
            user['today_progress'] = {
                'total_tasks': total_tasks,
                'completed_tasks': total_completed,
                'completion_rate': round((total_completed / total_tasks * 100) if total_tasks > 0 else 0, 1)
            }
        
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/progress')
def get_user_progress_api(user_id):
    """特定受講者の進捗を取得"""
    try:
        date_str = request.args.get('date', date.today().isoformat())
        progress = dashboard.get_user_progress(user_id, date_str)
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/tasks')
def get_user_tasks_api(user_id):
    """特定受講者のタスク詳細を取得"""
    try:
        date_str = request.args.get('date', date.today().isoformat())
        tasks = dashboard.get_user_tasks(user_id, date_str)
        return jsonify(tasks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/weekly')
def get_user_weekly_progress(user_id):
    """特定受講者の週間進捗を取得"""
    try:
        weekly_data = dashboard.get_weekly_progress(user_id)
        return jsonify(weekly_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/user/<int:user_id>')
def user_detail(user_id):
    """個別受講者の詳細ページ"""
    return render_template('user_detail.html', user_id=user_id)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)