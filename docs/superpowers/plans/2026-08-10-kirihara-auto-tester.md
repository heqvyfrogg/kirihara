# 桐原書店「きりはらの森の学校」自動テスト受験システム 実装計画書 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 桐原書店「きりはらの森の学校（フォレストテスト 生徒用）」において、指定年度のテスト一覧取得・問題JSON取得・Gemini APIバッチ解答（トークン極小化）・解答提出・結果取得までを自動実行するPython CLIツールを構築する。

**Architecture:** 責務ごとに分離されたモジュール構成（`models.py`, `utils.py`, `client.py`, `solver.py`, `cli.py`）。テスト全問を1回のリクエストで解くバッチ推論＋ローカルキャッシュにより、無料枠APIトークン・リクエスト数を極小化する。

**Tech Stack:** Python 3.10+, `requests`, `pydantic`, `google-genai`, `pytest`, `pytest-mock`

## Global Constraints
- **対象ドメイン**: `https://www.kirihara-morinogakko.jp`
- **HTTPヘッダー**: `X-APPLICATION-NAME: Moritest-Students` を付与
- **パスワード暗号化**: SHA-256（小文字16進数文字列）
- **APIトークン極小化**: テスト20問を一括1リクエストで解くプロンプト設計＋`cache.json` による既知問題の0トークン再利用
- **セキュリティ**: 生徒の個人情報（氏名・UUID等）はログ出力時に適切に保護

---

### Task 1: プロジェクト基盤とデータモデル定義 (`models.py`, `requirements.txt`)

**Files:**
- Create: `requirements.txt`
- Create: `kirihara/__init__.py`
- Create: `kirihara/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `UserInfo`, `TestItem`, `Option`, `Question`, `MainQuestion`, `TestQuestionSet`
  - `AnswerResult`, `QuestionAnswer`, `SubmittedPayload`

- [ ] **Step 1: Write the failing test for models**

```python
# tests/test_models.py
from kirihara.models import Option, Question, MainQuestion, TestQuestionSet, SubmittedPayload, QuestionAnswer, AnswerResult

def test_question_set_parsing():
    raw_json = {
        "id": 108161,
        "title": "8月10日（月）単語テスト",
        "bookName": "データベース3300 基本英単語・熟語",
        "count": 1,
        "mainQuestions": [
            {
                "id": 300733,
                "text": "日本語の意味に合う英語を選びなさい。",
                "type": 0,
                "questions": [
                    {
                        "id": 2453899,
                        "text": "（計画・提案など）を拒絶する<br>",
                        "audioUrl": None,
                        "imageUrl": None,
                        "answerCount": 1,
                        "options": [
                            {"id": 10237654, "text": "regret"},
                            {"id": 10237657, "text": "reject"}
                        ]
                    }
                ]
            }
        ]
    }
    q_set = TestQuestionSet.model_validate(raw_json)
    assert q_set.id == 108161
    assert len(q_set.mainQuestions) == 1
    assert q_set.mainQuestions[0].questions[0].options[1].text == "reject"

def test_submitted_payload_serialization():
    payload = SubmittedPayload(
        distributionId=94506,
        testAnswers=[
            QuestionAnswer(
                testQuestionId=2453899,
                results=[AnswerResult(id=10237657, order=0)]
            )
        ]
    )
    dumped = payload.model_dump()
    assert dumped["distributionId"] == 94506
    assert dumped["testAnswers"][0]["results"][0]["id"] == 10237657
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'kirihara')

- [ ] **Step 3: Implement `requirements.txt` and `kirihara/models.py`**

```txt
# requirements.txt
requests>=2.31.0
pydantic>=2.0.0
google-genai>=0.1.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

```python
# kirihara/__init__.py
"""Kirihara Auto Test Solver Package."""
__version__ = "1.0.0"
```

```python
# kirihara/models.py
from typing import List, Optional
from pydantic import BaseModel, Field

class Option(BaseModel):
    id: int
    text: str

class Question(BaseModel):
    id: int
    text: str
    audioUrl: Optional[str] = None
    imageUrl: Optional[str] = None
    questionNum: Optional[int] = None
    questionSource: Optional[str] = None
    answerCount: Optional[int] = 1
    options: List[Option] = Field(default_factory=list)

class MainQuestion(BaseModel):
    id: int
    text: str
    audioUrl: Optional[str] = None
    imageUrl: Optional[str] = None
    type: int = 0
    questions: List[Question] = Field(default_factory=list)

class TestQuestionSet(BaseModel):
    id: int
    title: str
    bookName: str
    count: int
    mainQuestions: List[MainQuestion] = Field(default_factory=list)

class TestItem(BaseModel):
    distributionId: int
    title: str
    bookName: str
    limitTime: Optional[int] = None
    questionCount: Optional[int] = None
    correctCount: Optional[int] = None
    status: Optional[int] = None  # 1: 未受験, 3: 完了, etc.

class AnswerResult(BaseModel):
    id: int
    order: int = 0

class QuestionAnswer(BaseModel):
    testQuestionId: int
    results: List[AnswerResult]

class SubmittedPayload(BaseModel):
    distributionId: int
    testAnswers: List[QuestionAnswer]
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_models.py -v`
Expected: PASS

---

### Task 2: ユーティリティモジュール (`utils.py`) の実装

**Files:**
- Create: `kirihara/utils.py`
- Create: `tests/test_utils.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str) -> str` (SHA-256 小文字16進)
  - `clean_html(text: str) -> str`
  - `simulate_delay(min_sec: float, max_sec: float)`

- [ ] **Step 1: Write the failing test for utils**

```python
# tests/test_utils.py
from kirihara.utils import hash_password, clean_html

def test_hash_password():
    # sha256("test_password") = 9f735e0df9a1ddc702bf0a1a7b83033f9f7153a00c29de82cedadc99572d2313
    assert hash_password("test_password") == "9f735e0df9a1ddc702bf0a1a7b83033f9f7153a00c29de82cedadc99572d2313"

def test_clean_html():
    raw = "（計画・提案など）を拒絶する<br>"
    assert clean_html(raw) == "（計画・提案など）を拒絶する"
    assert clean_html("We <u>persuaded</u> her") == "We persuaded her"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_utils.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `kirihara/utils.py`**

```python
# kirihara/utils.py
import hashlib
import re
import time
import random

def hash_password(password: str) -> str:
    """Hash password with SHA-256 and return hex string."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def clean_html(text: str) -> str:
    """Remove HTML tags like <br>, <u>, </u>, etc."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def simulate_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """Simulate human reading/answering delay."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_utils.py -v`
Expected: PASS

---

### Task 3: 桐原書店APIクライアント (`client.py`) の実装

**Files:**
- Create: `kirihara/client.py`
- Create: `tests/test_client.py`

**Interfaces:**
- Consumes: `kirihara.models.*`, `kirihara.utils.hash_password`
- Produces: `KiriharaClient` class
  - `login(account_name, password)`
  - `get_user_info()`
  - `get_tests(year=2026)`
  - `get_test_url(distribution_id)`
  - `fetch_question_set(json_url)`
  - `sync_start_answer(distribution_id)`
  - `submit_answers(payload)`

- [ ] **Step 1: Write the failing test for API client**

```python
# tests/test_client.py
import pytest
from unittest.mock import MagicMock
from kirihara.client import KiriharaClient
from kirihara.models import SubmittedPayload, QuestionAnswer, AnswerResult

def test_client_headers(mocker):
    client = KiriharaClient(session_cookie="dummy_session")
    assert client.headers["X-APPLICATION-NAME"] == "Moritest-Students"
    assert "SESSION=dummy_session" in client.headers.get("Cookie", "")

def test_get_tests_mocked(mocker):
    client = KiriharaClient(session_cookie="dummy")
    mock_get = mocker.patch("requests.Session.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [
            {"distributionId": 94506, "title": "8月10日（月）単語テスト", "bookName": "データベース3300", "status": 1}
        ]
    )
    tests = client.get_tests(year=2026)
    assert len(tests) == 1
    assert tests[0].distributionId == 94506
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_client.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `kirihara/client.py`**

```python
# kirihara/client.py
from typing import List, Optional, Dict, Any
import requests
from kirihara.models import TestItem, TestQuestionSet, SubmittedPayload
from kirihara.utils import hash_password

BASE_URL = "https://www.kirihara-morinogakko.jp"

class KiriharaClient:
    def __init__(self, session_cookie: Optional[str] = None):
        self.session = requests.Session()
        self.headers: Dict[str, str] = {
            "X-APPLICATION-NAME": "Moritest-Students",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        if session_cookie:
            self.session.cookies.set("SESSION", session_cookie)
            self.headers["Cookie"] = f"SESSION={session_cookie}"

    def login(self, account_name: str, password: str, one_time_password: Optional[str] = None) -> bool:
        """Login with account name and password (SHA-256 hashed)."""
        hashed_pw = hash_password(password)
        payload = {
            "accountName": account_name,
            "password": hashed_pw,
            "oneTimePassword": one_time_password
        }
        url = f"{BASE_URL}/kirihara/api/login"
        resp = self.session.post(url, json=payload, headers=self.headers)
        if resp.status_code == 200:
            # Update session cookie if returned
            if "SESSION" in resp.cookies:
                self.headers["Cookie"] = f"SESSION={resp.cookies['SESSION']}"
            return True
        return False

    def get_user_info(self) -> Dict[str, Any]:
        """Fetch current user info."""
        url = f"{BASE_URL}/kirihara/api/users/me?needsUserType=true&needsUserInfo=true&needsAccessCodes=true"
        resp = self.session.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def get_tests(self, year: int = 2026) -> List[TestItem]:
        """Fetch available tests list for given year."""
        url = f"{BASE_URL}/kirihara/api/students/tests?year={year}"
        resp = self.session.get(url, headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return [TestItem.model_validate(item) for item in data]

    def get_test_url(self, distribution_id: int) -> Dict[str, Any]:
        """Get static JSON URL for a test distribution."""
        url = f"{BASE_URL}/kirihara/api/students/test/{distribution_id}/url"
        resp = self.session.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def fetch_question_set(self, json_url: str) -> TestQuestionSet:
        """Download problem JSON from CloudFront/S3."""
        resp = self.session.get(json_url)
        resp.raise_for_status()
        return TestQuestionSet.model_validate(resp.json())

    def sync_start_answer(self, distribution_id: int) -> bool:
        """Notify server of test start with empty answers."""
        url = f"{BASE_URL}/kirihara/api/students/test/answer"
        payload = {"distributionId": distribution_id, "testAnswers": []}
        resp = self.session.put(url, json=payload, headers=self.headers)
        return resp.status_code == 200

    def submit_answers(self, payload: SubmittedPayload) -> Dict[str, Any]:
        """Submit final answers and trigger grading."""
        url = f"{BASE_URL}/kirihara/api/students/test/answer/submitted"
        resp = self.session.post(url, json=payload.model_dump(), headers=self.headers)
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_client.py -v`
Expected: PASS

---

### Task 4: トークン極小化AI解答エンジン (`solver.py`) の実装

**Files:**
- Create: `kirihara/solver.py`
- Create: `tests/test_solver.py`

**Interfaces:**
- Consumes: `kirihara.models.*`, `kirihara.utils.clean_html`
- Produces: `KiriharaSolver` class
  - `solve_test(question_set: TestQuestionSet, target_accuracy: float = 1.0) -> SubmittedPayload`
  - `cache_answers(key, data)` & `load_cached_answers(key)`

- [ ] **Step 1: Write the failing test for solver**

```python
# tests/test_solver.py
import json
from unittest.mock import MagicMock
from kirihara.solver import KiriharaSolver
from kirihara.models import TestQuestionSet, Option, Question, MainQuestion

def test_build_compact_prompt():
    solver = KiriharaSolver(api_key="mock_key")
    q_set = TestQuestionSet(
        id=108161,
        title="単語テスト",
        bookName="DB3300",
        count=1,
        mainQuestions=[
            MainQuestion(
                id=300733,
                text="日本語の意味に合う英語を選びなさい。",
                type=0,
                questions=[
                    Question(
                        id=2453899,
                        text="（計画・提案など）を拒絶する<br>",
                        options=[
                            Option(id=10237654, text="regret"),
                            Option(id=10237657, text="reject")
                        ]
                    )
                ]
            )
        ]
    )
    prompt = solver._build_compact_prompt(q_set)
    assert "2453899" in prompt
    assert "reject" in prompt

def test_solve_test_mocked_gemini(mocker):
    solver = KiriharaSolver(api_key="mock_key")
    mocker.patch.object(
        solver, "_call_gemini",
        return_value={"2453899": [10237657]}
    )
    q_set = TestQuestionSet(
        id=108161,
        title="単語テスト",
        bookName="DB3300",
        count=1,
        mainQuestions=[
            MainQuestion(
                id=300733,
                text="日本語の意味に合う英語を選びなさい。",
                type=0,
                questions=[
                    Question(
                        id=2453899,
                        text="（計画・提案など）を拒絶する",
                        options=[Option(id=10237654, text="regret"), Option(id=10237657, text="reject")]
                    )
                ]
            )
        ]
    )
    payload = solver.solve_test(distribution_id=94506, question_set=q_set)
    assert payload.distributionId == 94506
    assert len(payload.testAnswers) == 1
    assert payload.testAnswers[0].results[0].id == 10237657
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_solver.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `kirihara/solver.py`**

```python
# kirihara/solver.py
import json
import os
import re
import random
from typing import Dict, List, Any, Optional
from kirihara.models import TestQuestionSet, SubmittedPayload, QuestionAnswer, AnswerResult, Question, MainQuestion
from kirihara.utils import clean_html

CACHE_FILE = "kirihara_cache.json"

class KiriharaSolver:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_compact_prompt(self, question_set: TestQuestionSet) -> str:
        """Construct a minimal-token prompt for batch solving."""
        lines = [
            f"Subject: {question_set.bookName} / {question_set.title}",
            "Task: Solve all questions. Return ONLY a valid JSON map: {\"<question_id>\": [<choice_id(s)>]}",
            "Rules:",
            "1. Single-choice / Listening: return [chosen_choice_id]",
            "2. Ordering: return list of choice_ids in exact ordered sequence from 1st to last",
            "Questions:"
        ]
        for mq in question_set.mainQuestions:
            q_type_str = "Ordering" if mq.type == 1 else "Multiple Choice"
            lines.append(f"\n[Section {clean_html(mq.text)} ({q_type_str})]")
            for q in mq.questions:
                q_text = clean_html(q.text)
                if q.audioUrl:
                    # Extract word number if present in filename
                    m = re.search(r'Level_\d+_(\d+)_e\.mp3', q.audioUrl)
                    if m:
                        q_text += f" (Audio word #{m.group(1)})"
                options_str = " | ".join([f"{opt.id}:{clean_html(opt.text)}" for opt in q.options])
                lines.append(f"Q#{q.id}: {q_text} -> Options: [{options_str}]")
        return "\n".join(lines)

    def _call_gemini(self, prompt: str) -> Dict[str, List[int]]:
        """Call Gemini API using google-genai or direct request."""
        from google import genai
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        text = response.text.strip()
        return json.loads(text)

    def solve_test(self, distribution_id: int, question_set: TestQuestionSet, target_accuracy: float = 1.0) -> SubmittedPayload:
        cache_key = f"test_set_{question_set.id}"
        solved_map = self.cache.get(cache_key)

        if not solved_map:
            prompt = self._build_compact_prompt(question_set)
            solved_map = self._call_gemini(prompt)
            self.cache[cache_key] = solved_map
            self._save_cache()

        test_answers: List[QuestionAnswer] = []
        
        for mq in question_set.mainQuestions:
            for q in mq.questions:
                q_id_str = str(q.id)
                chosen_ids = solved_map.get(q_id_str, [])

                # Accuracy control (intentionally pick wrong answer if rolled)
                if target_accuracy < 1.0 and random.random() > target_accuracy and len(q.options) > 1:
                    wrong_opts = [opt.id for opt in q.options if opt.id not in chosen_ids]
                    if wrong_opts:
                        chosen_ids = [random.choice(wrong_opts)]

                if not chosen_ids and q.options:
                    chosen_ids = [q.options[0].id]

                if mq.type == 1:
                    # Ordering: order starts at 1
                    results = [AnswerResult(id=cid, order=idx+1) for idx, cid in enumerate(chosen_ids)]
                else:
                    # Single choice: order is 0
                    results = [AnswerResult(id=chosen_ids[0], order=0)]

                test_answers.append(QuestionAnswer(testQuestionId=q.id, results=results))

        return SubmittedPayload(distributionId=distribution_id, testAnswers=test_answers)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_solver.py -v`
Expected: PASS

---

### Task 5: CLIインターフェースとメイン実行スクリプト (`cli.py`, `main.py`) の実装

**Files:**
- Create: `kirihara/cli.py`
- Create: `main.py`
- Create: `.env.example`
- Create: `README.md`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `KiriharaClient`, `KiriharaSolver`, `utils.simulate_delay`
- Produces: CLI commands (`list`, `run`)

- [ ] **Step 1: Write the failing test for CLI**

```python
# tests/test_cli.py
from kirihara.cli import parse_args

def test_parse_args():
    args = parse_args(["list", "--year", "2026"])
    assert args.command == "list"
    assert args.year == 2026

    args_run = parse_args(["run", "94506", "--dry-run", "--target-accuracy", "90"])
    assert args_run.command == "run"
    assert args_run.distribution_id == 94506
    assert args_run.dry_run is True
    assert args_run.target_accuracy == 90.0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `kirihara/cli.py` and `main.py`**

```python
# kirihara/cli.py
import argparse
import sys
import os
from typing import Optional
from dotenv import load_dotenv
from kirihara.client import KiriharaClient
from kirihara.solver import KiriharaSolver
from kirihara.utils import simulate_delay

load_dotenv()

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Kirihara Auto Test Solver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    list_p = subparsers.add_parser("list", help="List available tests")
    list_p.add_argument("--year", type=int, default=2026, help="Target fiscal year")

    # run command
    run_p = subparsers.add_parser("run", help="Solve and submit a test")
    run_p.add_argument("distribution_id", type=int, help="Distribution ID of test")
    run_p.add_argument("--dry-run", action="store_true", help="Preview answers without submitting")
    run_p.add_argument("--human-like", action="store_true", help="Simulate realistic solving delay")
    run_p.add_argument("--target-accuracy", type=float, default=100.0, help="Target accuracy percentage (e.g. 90)")

    return parser.parse_args(args)

def run_cli():
    args = parse_args()
    session_cookie = os.environ.get("SESSION_COOKIE", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    client = KiriharaClient(session_cookie=session_cookie)

    if args.command == "list":
        try:
            user = client.get_user_info()
            print(f"Logged in as: {user.get('userInfo', {}).get('name', 'Student')}")
        except Exception as e:
            print(f"Warning: Could not fetch user info ({e})")

        tests = client.get_tests(year=args.year)
        print(f"\n--- Tests for Year {args.year} (Total: {len(tests)}) ---")
        print(f"{'ID':<8} {'Status':<10} {'Score':<8} {'Title':<30} {'Book':<25}")
        print("-" * 85)
        for t in tests:
            status_str = "Completed" if t.status == 3 else "Pending"
            score_str = f"{t.correctCount}/{t.questionCount}" if t.correctCount is not None else "-"
            print(f"{t.distributionId:<8} {status_str:<10} {score_str:<8} {t.title:<30} {t.bookName:<25}")

    elif args.command == "run":
        print(f"[*] Starting test solving for Distribution ID: {args.distribution_id}")
        url_info = client.get_test_url(args.distribution_id)
        json_url = url_info.get("jsonUrl")
        print(f"[*] Fetching question set from: {json_url}")
        
        q_set = client.fetch_question_set(json_url)
        print(f"[*] Test Title: {q_set.title} (Questions: {q_set.count})")

        if not args.dry_run:
            print("[*] Synchronizing test start state...")
            client.sync_start_answer(args.distribution_id)

        solver = KiriharaSolver(api_key=gemini_key)
        accuracy_ratio = args.target_accuracy / 100.0
        print(f"[*] Solving questions (Batch AI inference, Target Accuracy: {args.target_accuracy}%)...")
        payload = solver.solve_test(args.distribution_id, q_set, target_accuracy=accuracy_ratio)

        print("\n--- Solved Answers Preview ---")
        for ans in payload.testAnswers:
            res_str = ", ".join([f"ID:{r.id}(ord:{r.order})" for r in ans.results])
            print(f"Q#{ans.testQuestionId}: {res_str}")

        if args.dry_run:
            print("\n[!] Dry run mode enabled. Answers NOT submitted to server.")
            return

        if args.human_like:
            print("[*] Simulating human-like delay...")
            simulate_delay(3.0, 6.0)

        print("\n[*] Submitting answers to Kirihara server...")
        client.submit_answers(payload)
        print("[+] Successfully submitted!")

        # Verify score
        tests = client.get_tests(year=2026)
        for t in tests:
            if t.distributionId == args.distribution_id:
                print(f"[+] Result: {t.title} -> Correct: {t.correctCount}/{t.questionCount} (Status: {t.status})")
                break
```

```python
# main.py
from kirihara.cli import run_cli

if __name__ == "__main__":
    run_cli()
```

- [ ] **Step 4: Run all tests to verify 100% pass**
Run: `pytest tests/ -v`
Expected: ALL PASS

---

### Task 6: エンドツーエンド検証とドキュメント作成 (`README.md`, `.env.example`)

**Files:**
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Create `.env.example` and `README.md` with usage instructions**
- [ ] **Step 2: Run complete test suite and verify coverage**
Run: `pytest --verbose`
- [ ] **Step 3: Commit all changes**
