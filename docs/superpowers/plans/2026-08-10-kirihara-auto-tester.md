# kirihara-auto-tester 実装計画・タスク一覧

## 概要
桐原書店「きりはらの森の学校（フォレストテスト 生徒用）」向けの自動テスト解答CLIツールの開発タスク一覧です。

---

## 開発タスク

### Task 1: データモデル定義 (`models.py`)
- [x] Pydanticによる設問・選択肢・テスト情報・提出ペイロードの型定義
- [x] `tests/test_models.py` によるパース・シリアライズ検証

### Task 2: ユーティリティモジュール (`utils.py`)
- [x] パスワードのSHA-256ハッシュ化関数
- [x] HTMLタグ除去関数
- [x] JST日時変換およびテスト実施可能判定
- [x] East Asian Widthによる日本語文字幅計算とパディング
- [x] `tests/test_utils.py` による検証

### Task 3: APIクライアント実装 (`client.py`)
- [x] ログイン処理とCookieセッション管理
- [x] `x-application-name` ヘッダー制御
- [x] テスト一覧、問題URL、問題JSONの取得
- [x] テスト開始同期および解答提出
- [x] `tests/test_client.py` によるモック検証

### Task 4: 解答生成エンジン (`solver.py`)
- [x] バッチプロンプト生成ロジック
- [x] Gemini API呼び出しとJSONレスポンス解析
- [x] `kirihara_cache.json` によるローカルキャッシュ
- [x] `tests/test_solver.py` による検証

### Task 5: CLIインターフェース (`cli.py`, `main.py`)
- [x] `login`, `list`, `info`, `run` コマンドの実装
- [x] `--dry-run`, `--human-like`, `--target-accuracy`, `--wait` オプション
- [x] `tests/test_cli.py` による引数解析・動作検証

### Task 6: ドキュメントおよび設定ファイルの整備
- [x] `.env.example`, `.gitignore`, `requirements.txt` の作成
- [x] `README.md` の作成
