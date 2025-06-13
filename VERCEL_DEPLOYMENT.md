# Vercel デプロイ手順書

## 概要
Suna TODO アプリケーションをVercelにデプロイします。2つの独立したプロジェクトとして設定します：
- **学生用アプリ** (app.py)
- **インストラクター用アプリ** (instructor_app.py)

## 前提条件
✅ GitHubリポジトリ作成済み: `https://github.com/Ikki0518/Suna-ToDo.git`
✅ Vercel用設定ファイル準備済み
✅ Flask アプリケーションのWSGI対応完了

## 手順1: 学生用アプリのデプロイ

### 1.1 Vercelアカウント作成
1. [Vercel.com](https://vercel.com)にアクセス
2. **Sign Up** → **Continue with GitHub** でサインアップ

### 1.2 学生用アプリのプロジェクト作成
1. Vercelダッシュボードで **New Project** をクリック
2. **Import Git Repository** で `Ikki0518/Suna-ToDo` を選択
3. **Import** をクリック

### 1.3 学生用アプリの設定
**Project Settings:**
- **Project Name**: `suna-todo-student`
- **Framework Preset**: `Other`
- **Root Directory**: `./` (デフォルト)

**Environment Variables:**
以下の環境変数を追加：
```
FLASK_ENV=production
SECRET_KEY=your-random-secret-key-here
```

**Build Settings:**
- **Build Command**: (空のまま)
- **Output Directory**: (空のまま)

### 1.4 vercel.jsonの設定確認
リポジトリルートの `vercel.json` が以下の内容になっていることを確認：
```json
{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ],
  "env": {
    "FLASK_ENV": "production",
    "SECRET_KEY": "@secret_key"
  }
}
```

### 1.5 デプロイ実行
1. **Deploy** ボタンをクリック
2. デプロイ完了を待つ（3-5分程度）

## 手順2: インストラクター用アプリのデプロイ

### 2.1 新しいプロジェクト作成
1. 再度 **New Project** をクリック
2. 同じ `Ikki0518/Suna-ToDo` リポジトリを選択
3. **Import** をクリック

### 2.2 インストラクター用アプリの設定
**Project Settings:**
- **Project Name**: `suna-todo-instructor`
- **Framework Preset**: `Other`
- **Root Directory**: `./` (デフォルト)

**Environment Variables:**
```
FLASK_ENV=production
SECRET_KEY=your-random-secret-key-here
```

### 2.3 vercel.jsonの変更
インストラクター用プロジェクトの設定で、`vercel-instructor.json` を使用するように設定：

**方法A: ファイル名変更（推奨）**
1. プロジェクト設定で **Settings** → **General** を開く
2. **Build & Development Settings** で **Override** を有効にする
3. **Build Command**: `cp vercel-instructor.json vercel.json`

**方法B: ブランチ分割**
インストラクター用の別ブランチを作成してvercel.jsonを変更

### 2.4 デプロイ実行
1. **Deploy** ボタンをクリック
2. デプロイ完了を待つ

## 手順3: デプロイ後の確認

### 3.1 学生用アプリ
- **URL例**: `https://suna-todo-student.vercel.app`
- **動作確認**:
  - ログインページが表示される
  - demo / demo123 でログイン
  - TODO機能（追加、編集、エンターキー、タブキー）

### 3.2 インストラクター用アプリ
- **URL例**: `https://suna-todo-instructor.vercel.app`
- **動作確認**:
  - ダッシュボードが表示される
  - 学生一覧、統計情報の確認

## 手順4: カスタムドメイン設定（オプション）

### 4.1 ドメイン追加
各プロジェクトの設定で：
1. **Settings** → **Domains**
2. カスタムドメインを追加
   - 学生用: `student.your-domain.com`
   - インストラクター用: `instructor.your-domain.com`

## トラブルシューティング

### よくある問題

1. **ビルドエラー**
   ```
   Error: Python version not supported
   ```
   → requirements.txtの確認、Python3.9を指定

2. **ImportError**
   ```
   ModuleNotFoundError: No module named 'flask'
   ```
   → requirements.txtにFlask==2.3.3が含まれているか確認

3. **Static Files Not Found**
   ```
   404 on CSS/JS files
   ```
   → templatesフォルダのパスを確認

4. **Database Issues**
   ```
   sqlite3.OperationalError: database is locked
   ```
   → Vercelの読み取り専用ファイルシステムの制約
   → 本番用DBへの移行を検討（PostgreSQL等）

### デバッグ方法

1. **Function Logs**
   - Vercelダッシュボード → **Functions** → **View Function Logs**

2. **リアルタイムログ**
   - Vercel CLI: `vercel logs [PROJECT_URL]`

## 制限事項

1. **ファイルシステム**: 読み取り専用（SQLiteは制限あり）
2. **実行時間**: 関数の最大実行時間10秒（Hobbyプラン）
3. **メモリ**: 1024MB（Hobbyプラン）

## 次のステップ

1. **データベース移行**: PostgreSQL（Vercel Postgres）への移行
2. **モニタリング**: エラー追跡の設定
3. **パフォーマンス**: 必要に応じてキャッシュ設定
4. **セキュリティ**: HTTPS対応（Vercelは自動）

## 料金

- **Hobby Plan**: 無料（制限あり）
- **Pro Plan**: $20/月（チーム向け）
- **Enterprise**: カスタム価格

使用量によっては無料プランで十分運用可能です。