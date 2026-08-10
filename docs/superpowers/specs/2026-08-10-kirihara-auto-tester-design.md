# 桐原書店「きりはらの森の学校」自動テスト受験システム 設計仕様書

## 1. 概要

桐原書店が提供する学習テストプラットフォーム「きりはらの森の学校（フォレストテスト 生徒用）」における、テストの自動受験・解答提出・結果確認を行うPython CLIツール（`kirihara-auto-tester`）の設計仕様です。

---

## 2. システム構成

```text
kirihara-auto-tester/
├── kirihara/
│   ├── __init__.py
│   ├── client.py        # 桐原書店APIクライアント (認証, テスト一覧, 問題取得, 解答送信)
│   ├── solver.py        # Gemini API連携 解答生成エンジン & キャッシュ管理
│   ├── models.py        # 設問・選択肢・解答データ構造 (Pydantic)
│   ├── utils.py         # パスワードハッシュ化, ディレイ制御, 文字幅計算
│   └── cli.py           # CLIインターフェース (argparse)
├── tests/
│   ├── __init__.py
│   ├── test_client.py
│   ├── test_solver.py
│   ├── test_models.py
│   ├── test_utils.py
│   └── test_cli.py
├── .env.example
├── requirements.txt
├── main.py
└── README.md
```

---

## 3. APIクライアント仕様 (`KiriharaClient`)

桐原書店バックエンド（`https://www.kirihara-morinogakko.jp`）との通信を行います。

### 3.1 認証
- アカウント名およびパスワードのSHA-256ハッシュ値を用いて `/kirihara/api/login` へ `POST`。
- 返却されたCookieセッションを保持して各APIと通信。
- ヘッダー `x-application-name` をエンドポイントに応じて適切に設定（認証系: `COM`, 生徒API: `KFS`）。

### 3.2 主要エンドポイント
1. `GET /kirihara/api/users/me`: ユーザー情報・ログイン状態の取得
2. `GET /kirihara/api/students/tests?year={year}`: 配信テスト一覧の取得
3. `GET /kirihara/api/students/test/{distributionId}/url`: 問題JSONのURL取得
4. `GET /kirihara/api/students/tests/distributions/{distributionId}`: 制限時間・設問IDの取得
5. `GET {jsonUrl}`: 問題JSONのダウンロード
6. `PUT /kirihara/api/students/test/answer`: テスト開始同期
7. `POST /kirihara/api/students/test/answer/submitted`: 解答の一括送信

---

## 4. 解答エンジン仕様 (`KiriharaSolver`)

### 4.1 バッチ推論設計
- テスト全問を1つのプロンプトに集約し、1回のリクエストで解答JSONを取得。
- 余計な解説を含めず、設問IDと選択肢IDの対応関係のみをコンパクトに返却させる。

### 4.2 ローカルキャッシュ
- 設問テキストのハッシュ値をキーに `kirihara_cache.json` へ保存。
- 既知問題は外部APIを呼び出さずにキャッシュから即時解答。

### 4.3 出題形式への対応
1. 選択問題: 該当する選択肢IDを返却
2. 並び替え問題: 選択肢IDの順序リストを返却（`order: 1, 2, ...`）
3. リスニング問題: 音声ファイル名等を手がかりに解答を導出
