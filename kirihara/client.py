from typing import List, Optional, Dict, Any
import requests
from kirihara.models import TestItem, TestQuestionSet, SubmittedPayload
from kirihara.utils import hash_password

BASE_URL = "https://www.kirihara-morinogakko.jp"

class KiriharaClient:
    def __init__(self, session_cookie: Optional[str] = None):
        self.session = requests.Session()
        self.base_headers: Dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        if session_cookie:
            self.session.cookies.set("SESSION", session_cookie)

    def _headers(self, app_code: str = "COM", content_type: bool = False) -> Dict[str, str]:
        headers = dict(self.base_headers)
        headers["x-application-name"] = app_code
        headers["x-application_name"] = app_code
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def login(self, account_name: str, password: str, one_time_password: Optional[str] = None) -> bool:
        """Login with account name and password (SHA-256 hashed)."""
        hashed_pw = hash_password(password)
        payload = {
            "accountName": account_name,
            "password": hashed_pw
        }
        if one_time_password:
            payload["oneTimePassword"] = one_time_password

        # Try COM first, then MYP
        for app_code in ["COM", "MYP"]:
            url = f"{BASE_URL}/kirihara/api/login"
            headers = self._headers(app_code, content_type=True)
            resp = self.session.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                # Check if userType is authenticated (not 1 / LoggedOutUser)
                try:
                    user_info = self.get_user_info()
                    if user_info.get("userType", 1) != 1:
                        return True
                except Exception:
                    pass
        return False

    def ensure_authenticated(self, account_name: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """Ensure client is authenticated. If session is invalid, attempt login."""
        try:
            user_info = self.get_user_info()
            if user_info.get("userType", 1) != 1:
                return user_info
        except Exception:
            pass

        if account_name and password:
            if self.login(account_name, password):
                user_info = self.get_user_info()
                if user_info.get("userType", 1) != 1:
                    return user_info

        raise PermissionError(
            "Authentication failed. Please verify your KIRIHARA_ACCOUNT_NAME and KIRIHARA_PASSWORD in .env"
        )

    def get_user_info(self) -> Dict[str, Any]:
        """Fetch current user info."""
        url = f"{BASE_URL}/kirihara/api/users/me?needsUserType=true&needsUserInfo=true&needsAccessCodes=true"
        resp = self.session.get(url, headers=self._headers("COM"))
        resp.raise_for_status()
        return resp.json()

    def get_tests(self, year: int = 2026) -> List[TestItem]:
        """Fetch available tests list for given fiscal year."""
        url = f"{BASE_URL}/kirihara/api/students/tests?year={year}"
        resp = self.session.get(url, headers=self._headers("KFS"))
        resp.raise_for_status()
        data = resp.json()
        raw_tests = data.get("tests", []) if isinstance(data, dict) else data
        return [TestItem.model_validate(item) for item in (raw_tests or [])]

    def get_test_url(self, distribution_id: int) -> Dict[str, Any]:
        """Get static JSON URL for a test distribution."""
        url = f"{BASE_URL}/kirihara/api/students/test/{distribution_id}/url"
        resp = self.session.get(url, headers=self._headers("KFS"))
        resp.raise_for_status()
        return resp.json()

    def fetch_question_set(self, json_url: str) -> TestQuestionSet:
        """Download problem JSON from CloudFront/S3."""
        resp = self.session.get(json_url, headers=self.base_headers)
        resp.raise_for_status()
        return TestQuestionSet.model_validate(resp.json())

    def sync_start_answer(self, distribution_id: int) -> bool:
        """Notify server of test start with empty answers."""
        url = f"{BASE_URL}/kirihara/api/students/test/answer"
        payload = {"distributionId": distribution_id, "testAnswers": []}
        resp = self.session.put(url, json=payload, headers=self._headers("KFS", content_type=True))
        return resp.status_code == 200

    def submit_answers(self, payload: SubmittedPayload) -> Dict[str, Any]:
        """Submit final answers and trigger grading."""
        url = f"{BASE_URL}/kirihara/api/students/test/answer/submitted"
        resp = self.session.post(url, json=payload.model_dump(), headers=self._headers("KFS", content_type=True))
        resp.raise_for_status()
        return resp.json()
