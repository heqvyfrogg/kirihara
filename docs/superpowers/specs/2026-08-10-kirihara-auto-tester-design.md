# 桐原書店「きりはらの森の学校」自動テスト受験システム 設計仕様書 (Design Spec)

- **作成日**: 2026-08-10
- **ステータス**: 承認済み (Approved)
- **対象ドメイン**: `www.kirihara-morinogakko.jp` (きりはらの森の学校 / Moritest Students)

---

## 1. 概要 (Overview)

桐原書店が提供する教育テストプラットフォーム「きりはらの森の学校（フォレストテスト 生徒用）」における、テストの自動受験・自動解答送信・結果確認を行うPythonベースの自動化ツール（`kirihara-auto-tester`）の仕様を定義する。

`README_anonymized.md` および HTTPアーカイブ (`network_capture.har`) のトラフィック解析に基づき、公式の通信仕様と暗号化（SHA-256パスワードハッシュ）に完全準拠したAPIクライアントおよびGemini APIを活用した高精度AI解答エンジンを構築する。

---

## 2. システムアーキテクチャ & ディレクトリ構成

```
kirihara-auto-tester/
├── kirihara/
│   ├── __init__.py
│   ├── client.py        # 桐原書店APIクライアント (認証, テスト一覧, 問題取得, 解答送信)
│   ├── solver.py        # Gemini API連携 自動問題解析・解答導出エンジン
│   ├── models.py        # 問題・選択肢・解答データ構造 (Pydantic / Dataclass)
│   ├── utils.py         # SHA-256ハッシュ化, ディレイ制御, フォーマッタ
│   └── cli.py           # CLIコマンドライン操作インターフェース (Rich / Typer)
├── tests/
│   ├── __init__.py
│   ├── test_client.py   # APIクライアント単体テスト (モック使用)
│   └── test_solver.py   # 解答エンジン単体テスト (全問題形式)
├── .env.example         # 認証設定テンプレート
├── requirements.txt     # 依存ライブラリ一覧
├── main.py              # メインエントリーポイント
└── README.md            # 利用手順書
```

---

## 3. APIクライアント仕様 (KiriharaClient)

桐原書店バックエンド（`https://www.kirihara-morinogakko.jp`）との通信を担う。

### 3.1 認証とヘッダー
- **必須HTTPヘッダー**:
  - `X-APPLICATION-NAME`: `Moritest-Students` (または `COM`/`MYP`)
  - `User-Agent`: 標準的なブラウザUser-Agent
  - `Content-Type`: `application/json`
- **認証方式**:
  - 方式A (推奨): `SESSION` Cookieを直接 `.env` に設定してセッション再利用。
  - 方式B: アカウント名 + パスワード（SHA-256 ハッシュ値を小文字16進文字列化）を用いて `/kirihara/api/login` へ `POST`。

### 3.2 主要APIエンドポイント
1. `GET /kirihara/api/users/me?needsUserType=true&needsUserInfo=true&needsAccessCodes=true`
   - ユーザー情報とセッション有効性を検証。
2. `GET /kirihara/api/students/tests?year={year}`
   - 当該年度の配信テスト一覧（`distributionId`, `title`, `bookName`, `status`, `correctCount` 等）を取得。
3. `GET /kirihara/api/students/test/{distributionId}/url`
   - テスト問題JSONの静的配信URL（S3/CloudFront URL）を取得。
4. `GET /kirihara/api/students/tests/distributions/{distributionId}`
   - テスト制限時間および設問IDリスト（`remainingTime`, `testAnswers`）を取得。
5. `GET {jsonUrl}`
   - S3/CloudFront上の問題JSON（大問、小問、選択肢、音声URL等）をダウンロード。
6. `PUT /kirihara/api/students/test/answer`
   - テスト開始時の空解答状態（`{"distributionId": id, "testAnswers": []}`）をサーバーに同期。
7. `POST /kirihara/api/students/test/answer/submitted`
   - 最終解答（`{"distributionId": id, "testAnswers": [...]}`）を一括送信して採点を実行。

---

## 4. AI解答エンジン仕様 (KiriharaSolver) & トークン節約最適化

Google AI APIの無料枠制限（RPM/RPD/トークン数）に配慮し、**徹底的なトークン・APIコール削減設計**を採用する。

### 4.1 トークン・リクエスト削減の具体策
1. **全問一括バッチ推論 (1リクエスト完結)**:
   - 20問を1問ずつAPIに送る（20リクエスト）のではなく、テスト全問を**1つのコンパクトなプロンプトにまとめて1回のリクエスト**で解決。
   - API呼び出し回数を **20回 → 1回** に削減（約95%削減）。
2. **極小プロンプト & 出力フォーマット**:
   - HTMLタグや無駄なメタデータを除去し、問題文・選択肢ID・テキストのみを最小構成で送信。
   - レスポンスは解説不要の純粋なコンパクトJSON（`{"qId": [choiceIds...]}`）形式のみを指定し、出力トークン消費を最小化（数百トークン以内）。
3. **ローカル結果キャッシュ (0トークン化)**:
   - 一度解いた問題や単語データはローカルの `cache.json` に自動記録。同一テストの再受験や既知問題は **API呼び出しゼロ（0トークン）** で解答。
4. **軽量・高効率モデル (`gemini-2.5-flash`) の採用**:
   - 無料枠制限に余裕のある超高速・低コストな Flash モデルを使用。

### 4.2 出題形式ごとの解答ロジック
1. **日英・英日選択 (type=0)**:
   - 日本語の意味または英単語に対応する選択肢IDを特定。
   - `results: [{"id": choice_id, "order": 0}]`
2. **下線部和訳 / 空所補充 (type=0)**:
   - 英文の文脈に最も合致する選択肢IDを特定。
   - `results: [{"id": choice_id, "order": 0}]`
3. **語順整序 / 並び替え (type=1)**:
   - 正しい英文になる単語順序（1始まり）を決定。
   - `results: [{"id": id1, "order": 1}, {"id": id2, "order": 2}, ...]`
4. **リスニング音声問題**:
   - 音声URLの単語番号（例: `Level_6_1795_e.mp3` → 単語番号 1795）やローカル辞書と照合、必要最小限の推論で選択肢を特定。

---

## 5. CLIインターフェース & 機能仕様

### 5.1 コマンドライン引数
- `python main.py list`: 配信中のテスト一覧（受験済み・未受験）を表形式で表示。
- `python main.py run <distributionId>`: 指定したテストを自動解答・提出。
- `python main.py run <distributionId> --dry-run`: 解答の送信を行わず、AIの推論結果・選択肢プレビューのみ表示。
- `python main.py run <distributionId> --human-like`: 各問に1〜3秒のランダムディレイを挿入し、自然な所要時間で提出。
- `python main.py run <distributionId> --target-accuracy 90`: 意図的に90%（20問中18問正解など）の正答率になるよう調整。

---

## 6. エラーハンドリング・セキュリティ

- **認証失効時の検知**: 401 Unauthorized または セッション切れを検知した場合、即座に分かりやすいエラーメッセージを表示。
- **リトライポリシー**: S3/CloudFrontからの問題JSON取得やGemini API呼び出しには指数バックオフ付きのリトライを実施。
- **個人情報の保護**: 出力ログやレポートにおいて、生徒の個人情報（氏名・学校名・クラス名・UUID）を適切にマスキングまたは保護。
