# Suna TODO アプリケーション デプロイメントガイド

## アプリケーション概要

このプロジェクトには2つの独立したFlaskアプリケーションが含まれています：

1. **学生用 TODO アプリ** (`app.py`)
   - ポート: 5004 (開発時)
   - 機能: タスク管理、進捗追跡、階層的タスク組織
   - URL: `/`

2. **インストラクター管理ダッシュボード** (`instructor_app.py`)
   - ポート: 5005 (開発時)
   - 機能: 学生管理、進捗監視、統計表示
   - URL: `/`

## デプロイメントオプション

### オプション 1: Heroku デプロイ

#### 学生用アプリ
```bash
# Herokuアプリを作成
heroku create suna-todo-student

# 環境変数を設定
heroku config:set FLASK_ENV=production --app suna-todo-student

# Procfileを使用してデプロイ
git add .
git commit -m "Deploy student app"
git push heroku main
```

#### インストラクター用アプリ
```bash
# 別のHerokuアプリを作成
heroku create suna-todo-instructor

# instructor用のProcfileを使用
cp Procfile.instructor Procfile
git add .
git commit -m "Deploy instructor app"
git push heroku main
```

### オプション 2: Render デプロイ

#### 学生用アプリ
- リポジトリをRenderに接続
- ビルドコマンド: `pip install -r requirements.txt`
- 開始コマンド: `gunicorn app:app --bind 0.0.0.0:$PORT`

#### インストラクター用アプリ
- 別のRenderサービスを作成
- ビルドコマンド: `pip install -r requirements.txt`
- 開始コマンド: `gunicorn instructor_app:app --bind 0.0.0.0:$PORT`

### オプション 3: Railway デプロイ

#### 設定
1. Railwayにリポジトリを接続
2. 2つの別々のサービスを作成
3. 各サービスに適切な開始コマンドを設定

## 環境変数

### 必要な環境変数
- `FLASK_ENV`: `production`
- `SECRET_KEY`: セッション管理用の秘密鍵

### オプション環境変数
- `DATABASE_URL`: 外部データベースを使用する場合
- `PORT`: デプロイ先で自動設定されます

## データベース

現在はSQLiteを使用していますが、本番環境では以下を推奨：
- PostgreSQL (Heroku Postgres)
- MySQL
- 他のリレーショナルデータベース

## ファイル構成

```
todo-app-suna/
├── app.py                 # 学生用アプリ
├── instructor_app.py      # インストラクター用アプリ
├── requirements.txt       # Python依存関係
├── Procfile              # 学生用アプリのデプロイ設定
├── Procfile.instructor   # インストラクター用アプリのデプロイ設定
├── templates/            # HTMLテンプレート
├── static/              # 静的ファイル (CSS, JS, 画像)
└── .gitignore           # Git除外設定
```

## セキュリティ考慮事項

1. SECRET_KEYを環境変数として設定
2. 本番データベースの設定
3. HTTPS対応
4. CORS設定の確認
5. 認証システムの強化

## モニタリングとログ

- アプリケーションログの監視
- エラー追跡の設定
- パフォーマンス監視
- アクセス統計の収集