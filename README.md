# AI スクール TODOアプリ & 講師管理システム

AI スクール受講者向けのTODO管理アプリケーションと、講師・管理者向けの受講者進捗管理ダッシュボードのセットです。

## システム構成

### 1. 受講者用 TODO アプリ (`app.py` - ポート5004)
AI スクール受講者が日々のタスクを管理するためのアプリケーション

### 2. 講師用管理ダッシュボード (`instructor_app.py` - ポート5005)
講師・管理者が受講者の進捗を監視・管理するためのダッシュボード

## 受講者用 TODO アプリの機能

### 基本機能
- ✅ 日次タスクの追加・編集・削除・完了管理
- 🔄 定常タスク（毎日のルーチン）の管理
- 📊 インデント機能によるタスクの階層化
- 👤 ユーザー認証・アカウント管理
- 📅 日付ベースのタスク管理
- 💾 SQLiteデータベースでのデータ永続化

### UI・UX機能
- 📱 Apple Notes風の美しいデザイン
- 🖱️ ドラッグ&ドロップによるタスク並び替え
- ⚡ リアルタイムでの進捗更新
- 📱 レスポンシブデザイン（モバイル対応）

## 講師用管理ダッシュボードの機能

### 統計・概要機能
- 📊 **全体統計**: 総受講者数、アクティブユーザー数、平均完了率
- 👥 **受講者一覧**: 全受講者の今日の進捗状況を一覧表示
- 📈 **リアルタイム更新**: 5分ごとの自動データ更新

### 個別受講者管理
- 👤 **詳細進捗表示**: 各受講者の日次・定常タスクの完了状況
- 📅 **日付別進捗**: 任意の日付の進捗状況を確認
- 📊 **週間進捗チャート**: 過去7日間の完了率推移を視覚化
- ✅ **タスク詳細表示**: 完了・未完了タスクの具体的な内容を確認

### 監視・分析機能
- 🎯 **完了率計算**: 日次タスクと定常タスクを合わせた総合完了率
- 📈 **進捗トレンド**: 受講者ごとの学習進捗の傾向分析
- ⚠️ **アラート機能**: 進捗が遅れている受講者の特定

## セットアップ手順

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 受講者用 TODO アプリの起動

```bash
python app.py
```

受講者用アプリは `http://localhost:5004` で起動します。

### 3. 講師用管理ダッシュボードの起動

別のターミナルで以下を実行：

```bash
python instructor_app.py
```

講師用ダッシュボードは `http://localhost:5005` で起動します。

### 4. 初期データについて

初回起動時に以下のデモアカウントが自動作成されます：
- **ユーザー名**: demo
- **パスワード**: demo123

このアカウントでログインして機能をテストできます。

## 使用方法

### 受講者用 TODO アプリの使用方法

#### 1. ログイン・アカウント作成
- 初回利用時は「新規登録」からアカウントを作成
- 既存アカウントでログイン
- デモアカウント（demo/demo123）でのテスト利用も可能

#### 2. 日次タスクの管理
- **追加**: 右上の「+」ボタンでタスクを追加
- **完了**: タスクをクリックして完了状態に切り替え
- **編集**: タスクをダブルクリックして内容を編集
- **削除**: タスクの「×」ボタンで削除
- **インデント**: Tabキーで子タスクとして階層化

#### 3. 定常タスクの管理
- 毎日繰り返すルーチンタスクを管理
- 日次タスクとは別に管理され、毎日リセット
- 定常タスクセクションで追加・編集・削除が可能

#### 4. 日付別の進捗管理
- カレンダーで日付を選択して過去・未来のタスクを確認
- 各日付ごとに独立したタスクリストを管理

### 講師用管理ダッシュボードの使用方法

#### 1. ダッシュボード概要
- メインページで全体統計と受講者一覧を確認
- 「更新」ボタンで最新データを取得
- 5分ごとに自動更新

#### 2. 受講者の進捗監視
- 受講者カードをクリックして詳細ページを表示
- 今日の進捗率と完了タスク数を一覧で確認
- 進捗が低い受講者を素早く特定

#### 3. 個別受講者の詳細分析
- **日別進捗**: 日付を変更して任意の日の進捗を確認
- **タスク詳細**: 完了・未完了の具体的なタスク内容を表示
- **週間トレンド**: 過去7日間の完了率推移をチャートで確認

#### 4. 進捗データの活用
- 定常タスクと日次タスクの完了率を総合評価
- 学習継続状況や課題の特定
- 個別指導やフォローアップの優先順位付け

## 技術仕様

### 受講者用 TODO アプリ
- **フレームワーク**: Flask
- **データベース**: SQLite3 (`ai_school_todos.db`)
- **認証**: セッションベース認証（パスワードハッシュ化）
- **UI**: Apple Notes風カスタムデザイン

### 講師用管理ダッシュボード
- **フレームワーク**: Flask
- **データベース**: 受講者用アプリと同じSQLiteファイルを参照
- **UI**: モダンなグラス・モーフィズムデザイン
- **チャート**: HTML/CSS/JavaScriptによる軽量チャート実装

### データベーススキーマ

```sql
-- ユーザーテーブル
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 日次タスクテーブル
CREATE TABLE daily_tasks (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    completed BOOLEAN DEFAULT 0,
    date TEXT NOT NULL,
    indent INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 定常タスクテーブル
CREATE TABLE routine_tasks (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 定常タスク完了記録テーブル
CREATE TABLE routine_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    routine_id TEXT NOT NULL,
    date TEXT NOT NULL,
    completed BOOLEAN DEFAULT 0,
    UNIQUE(user_id, routine_id, date),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

## API エンドポイント

### 受講者用 TODO アプリ (`app.py`)

#### 認証関連
- `GET /login` - ログインページ表示
- `POST /login` - ログイン処理
- `GET /register` - 新規登録ページ表示
- `POST /register` - 新規登録処理
- `GET /logout` - ログアウト処理

#### タスク管理API
- `GET /` - メインTODOページ（ログイン必須）
- `GET /api/tasks/<date_str>` - 指定日のタスク一覧取得
- `POST /api/tasks` - 新しい日次タスクを追加
- `PUT /api/tasks/<task_id>` - タスクの更新（内容・完了状態・インデント）
- `DELETE /api/tasks/<task_id>` - タスクの削除
- `POST /api/reorder` - タスクの並び順変更

#### 定常タスク管理API
- `POST /api/routine` - 新しい定常タスクを追加
- `PUT /api/routine/<task_id>` - 定常タスクの更新
- `DELETE /api/routine/<task_id>` - 定常タスクの削除
- `POST /api/routine/toggle` - 定常タスクの完了状態切り替え

### 講師用管理ダッシュボード (`instructor_app.py`)

#### ダッシュボード表示
- `GET /` - メインダッシュボードページ
- `GET /user/<int:user_id>` - 個別受講者詳細ページ

#### 統計・データ取得API
- `GET /api/stats` - 全体統計（総受講者数、アクティブユーザー数、平均完了率）
- `GET /api/users` - 全受講者一覧と今日の進捗情報
- `GET /api/users/<int:user_id>/progress?date=<date>` - 特定受講者の指定日進捗
- `GET /api/users/<int:user_id>/tasks?date=<date>` - 特定受講者の指定日タスク詳細
- `GET /api/users/<int:user_id>/weekly` - 特定受講者の週間進捗データ

## ファイル構成

```
todo-app-suna/
├── app.py                          # 受講者用TODOアプリ（ポート5004）
├── instructor_app.py               # 講師用管理ダッシュボード（ポート5005）
├── ai_school_todos.db             # SQLiteデータベース（共有）
├── requirements.txt               # Python依存関係
├── README.md                      # このファイル
└── templates/                     # HTMLテンプレート
    ├── ai_school_todo.html        # 受講者用メインページ
    ├── login.html                 # ログインページ
    ├── register.html              # 新規登録ページ
    ├── instructor_dashboard.html  # 講師用ダッシュボード
    └── user_detail.html           # 個別受講者詳細ページ
```

## トラブルシューティング

### よくある問題

1. **データベースエラー**
   - アプリケーション起動時に自動的にデータベースが作成されます
   - 権限エラーの場合は、ディレクトリの書き込み権限を確認
   - 複数のアプリが同じデータベースファイルを共有するため、同時アクセスによる問題が発生する可能性があります

2. **ポートエラー**
   - 受講者用アプリ（ポート5004）と講師用ダッシュボード（ポート5005）が使用中の場合は、各ファイルの最後の行でポート番号を変更してください
   - 同時に両方のアプリを起動する必要があります

3. **認証エラー**
   - セッションが切れた場合は再ログインが必要
   - ブラウザのクッキーをクリアして再試行

4. **データ同期の問題**
   - 講師用ダッシュボードは受講者のデータをリアルタイムで表示
   - データが更新されない場合は「更新」ボタンをクリック

### 推奨環境
- Python 3.7以上
- モダンWebブラウザ（Chrome、Firefox、Safari、Edge）
- 1GB以上の空きメモリ

## セキュリティ考慮事項

- パスワードはSHA-256でハッシュ化して保存
- セッション管理にはFlaskの組み込み機能を使用
- 本番環境では以下の追加セキュリティ対策を推奨：
  - HTTPS通信の有効化
  - より強力なパスワードポリシー
  - レート制限の実装
  - CSRFトークンの実装

## 今後の拡張予定

- 📊 より詳細な進捗分析機能
- 📧 メール通知機能
- 📱 モバイルアプリ版
- 🔄 他のLMSとの連携
- 📈 長期的な学習データ分析
- 👥 グループ管理機能

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

プルリクエストやイシューの報告を歓迎します。

## 更新履歴

- **v2.0.0**: AI スクール対応版（2025年6月）
  - 受講者用TODOアプリの全面リニューアル
  - ユーザー認証システムの実装
  - 日次タスクと定常タスクの分離管理
  - Apple Notes風UIデザインの採用
  - 講師用管理ダッシュボードの新規開発
  - リアルタイム進捗監視機能
  - 週間進捗チャート機能
  - レスポンシブデザインの改善

- **v1.0.0**: 初回リリース
  - 基本的なToDo管理機能
  - Suna AI連携機能
  - レスポンシブWebデザイン