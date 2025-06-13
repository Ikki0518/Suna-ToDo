# Render.com デプロイ手順

## 手順1: GitHubリポジトリの作成

1. [GitHub](https://github.com)にログイン
2. 新しいリポジトリを作成（例: `suna-todo-app`）
3. ローカルからプッシュ:

```bash
# リモートリポジトリを追加
git remote add origin https://github.com/YOUR_USERNAME/suna-todo-app.git

# コードをプッシュ
git push -u origin main
```

## 手順2: Render.comでのデプロイ

### 2.1 アカウント作成
1. [Render.com](https://render.com)にアクセス
2. GitHubアカウントでサインアップ

### 2.2 学生用アプリのデプロイ

1. **New +** → **Web Service** を選択
2. **Connect GitHub** でリポジトリを接続
3. 以下の設定を入力:
   - **Name**: `suna-todo-student`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `FLASK_ENV` = `production`
     - `SECRET_KEY` = ランダムな文字列（自動生成）

4. **Create Web Service** をクリック

### 2.3 インストラクター用アプリのデプロイ

1. 再度 **New +** → **Web Service** を選択
2. 同じリポジトリを選択
3. 以下の設定を入力:
   - **Name**: `suna-todo-instructor`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn instructor_app:app --bind 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `FLASK_ENV` = `production`
     - `SECRET_KEY` = ランダムな文字列（自動生成）

4. **Create Web Service** をクリック

## 手順3: デプロイ後の確認

### 学生用アプリ
- URL: `https://suna-todo-student.onrender.com`
- 機能確認:
  - ログイン（demo / demo123）
  - タスク追加・編集
  - エンターキーでの位置指定追加
  - タブキーでのインデント

### インストラクター用アプリ
- URL: `https://suna-todo-instructor.onrender.com`
- 機能確認:
  - ダッシュボード表示
  - 学生一覧
  - 統計情報

## 手順4: カスタムドメイン設定（オプション）

1. Render.comの各サービス設定で **Custom Domain** を選択
2. 独自ドメインを設定（例: `student.suna-todo.com`, `instructor.suna-todo.com`）

## トラブルシューティング

### よくある問題

1. **ビルドエラー**
   - `requirements.txt` の依存関係を確認
   - Python バージョンを確認

2. **起動エラー**
   - Start Command が正しいか確認
   - 環境変数が設定されているか確認

3. **データベースエラー**
   - SQLiteファイルが作成されているか確認
   - 初期データが正しく投入されているか確認

### ログの確認
1. Render.comダッシュボードで各サービスを選択
2. **Logs** タブでエラーログを確認

## 無料プランの制限事項

- スリープ機能: 15分間アクセスがないとスリープ
- 起動時間: スリープから復帰に30-60秒
- 月間750時間の稼働時間制限

## 料金情報

- **Free Tier**: 無料（制限あり）
- **Starter**: $7/月（スリープなし、カスタムドメイン対応）
- **Standard**: $25/月（より高性能）

## 次のステップ

1. デプロイ完了後、URLをチームに共有
2. 本番環境でのテスト実施
3. 必要に応じてデータベースの本格移行（PostgreSQL等）
4. モニタリング・ログ監視の設定