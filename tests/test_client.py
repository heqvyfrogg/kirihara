# tests/test_client.py
import pytest
from unittest.mock import MagicMock
from kirihara.client import KiriharaClient
from kirihara.models import SubmittedPayload, QuestionAnswer, AnswerResult

def test_client_headers():
    client = KiriharaClient(session_cookie="test_session_123")
    headers = client._headers("COM")
    assert headers["x-application-name"] == "COM"
    assert client.session.cookies.get("SESSION") == "test_session_123"

def test_login(mocker):
    client = KiriharaClient()
    mock_post = mocker.patch("requests.Session.post")
    mock_resp = MagicMock(status_code=200)
    mock_post.return_value = mock_resp

    mocker.patch.object(client, "get_user_info", return_value={"userType": 8, "userInfo": {"name": "Test Student"}})

    success = client.login("test_user", "password123")
    assert success is True

def test_ensure_authenticated(mocker):
    client = KiriharaClient()
    mocker.patch.object(client, "login", return_value=True)
    mocker.patch.object(client, "get_user_info", side_effect=[{"userType": 1}, {"userType": 8, "userInfo": {"name": "Test"}}])
    user = client.ensure_authenticated("test_user", "pass")
    assert user["userInfo"]["name"] == "Test"

def test_get_user_info(mocker):
    client = KiriharaClient(session_cookie="sess")
    mock_get = mocker.patch("requests.Session.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"userType": 8, "userInfo": {"name": "Test Student"}}
    )
    user = client.get_user_info()
    assert user["userInfo"]["name"] == "Test Student"

def test_get_tests(mocker):
    client = KiriharaClient(session_cookie="sess")
    mock_get = mocker.patch("requests.Session.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "now": "2026-08-10T00:00:00.000Z",
            "tests": [
                {"distributionId": 94506, "title": "8月10日（月）単語テスト", "bookName": "データベース3300", "status": 1}
            ]
        }
    )
    tests = client.get_tests(year=2026)
    assert len(tests) == 1
    assert tests[0].distributionId == 94506

def test_get_test_url(mocker):
    client = KiriharaClient(session_cookie="sess")
    mock_get = mocker.patch("requests.Session.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"jsonUrl": "https://example.com/test.json", "title": "Test Title"}
    )
    url_info = client.get_test_url(94506)
    assert url_info["jsonUrl"] == "https://example.com/test.json"

def test_fetch_question_set(mocker):
    client = KiriharaClient(session_cookie="sess")
    mock_get = mocker.patch("requests.Session.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "id": 108161,
            "title": "単語テスト",
            "bookName": "DB3300",
            "count": 1,
            "mainQuestions": []
        }
    )
    q_set = client.fetch_question_set("https://example.com/test.json")
    assert q_set.id == 108161

def test_sync_start_answer(mocker):
    client = KiriharaClient(session_cookie="sess")
    mock_put = mocker.patch("requests.Session.put")
    mock_put.return_value = MagicMock(status_code=200)
    assert client.sync_start_answer(94506) is True

def test_submit_answers(mocker):
    client = KiriharaClient(session_cookie="sess")
    mock_post = mocker.patch("requests.Session.post")
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
    payload = SubmittedPayload(
        distributionId=94506,
        testAnswers=[QuestionAnswer(testQuestionId=1, results=[AnswerResult(id=10, order=0)])]
    )
    resp = client.submit_answers(payload)
    assert resp == {}
