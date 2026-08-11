# tests/test_utils.py
from datetime import datetime, timezone, timedelta
from kirihara.utils import (
    hash_password, clean_html, simulate_delay,
    parse_iso_datetime, format_jst, get_test_availability, JST
)

def test_hash_password():
    assert hash_password("test_password") == "10a6e6cc8311a3e2bcc09bf6c199adecd5dd59408c343e926b129c4914f3cb01"

def test_clean_html():
    raw = "（計画・提案など）を拒絶する<br>"
    assert clean_html(raw) == "（計画・提案など）を拒絶する"
    assert clean_html("We <u>persuaded</u> her") == "We persuaded her"
    assert clean_html(None) == ""

def test_get_display_width_and_pad_text():
    from kirihara.utils import get_display_width, pad_text
    assert get_display_width("abc") == 3
    assert get_display_width("単語テスト") == 10  # 5 full-width chars * 2 = 10
    
    padded = pad_text("テスト", 10)
    assert get_display_width(padded) == 10
    assert padded == "テスト    "

    padded_center = pad_text("10/10", 8, align="center")
    assert get_display_width(padded_center) == 8

def test_parse_iso_datetime():
    dt = parse_iso_datetime("2026-08-10T02:20:00.000Z")
    assert dt is not None
    assert dt.hour == 11  # 02:20 UTC = 11:20 JST
    assert dt.minute == 20

def test_get_test_availability_completed():
    status_label, time_hint, is_open = get_test_availability(
        "2026-08-01T00:00:00.000Z", "2026-08-02T00:00:00.000Z", status=3
    )
    assert "完了" in status_label
    assert is_open is False

def test_get_test_availability_upcoming():
    # Far in future
    status_label, time_hint, is_open = get_test_availability(
        "2099-01-01T00:00:00.000Z", "2099-01-02T00:00:00.000Z", status=None
    )
    assert "開始前" in status_label
    assert is_open is False

def test_sort_tests():
    from kirihara.utils import sort_tests
    from kirihara.models import TestItem

    t1 = TestItem(distributionId=100, title="B_Test", bookName="BookB", startAt="2026-08-01T00:00:00.000Z", correctCount=5, questionCount=10, status=3)
    t2 = TestItem(distributionId=200, title="A_Test", bookName="BookA", startAt="2026-08-10T00:00:00.000Z", correctCount=10, questionCount=10, status=3)
    t3 = TestItem(distributionId=50, title="C_Test", bookName="BookC", startAt="2026-07-01T00:00:00.000Z", correctCount=0, questionCount=10, status=None)

    # Sort by ID
    by_id = sort_tests([t1, t2, t3], sort_by="id")
    assert [t.distributionId for t in by_id] == [50, 100, 200]

    # Sort by score reverse (highest first)
    by_score = sort_tests([t1, t2, t3], sort_by="score", reverse=True)
    assert [t.correctCount for t in by_score] == [10, 5, 0]

    # Sort by title
    by_title = sort_tests([t1, t2, t3], sort_by="title")
    assert [t.title for t in by_title] == ["A_Test", "B_Test", "C_Test"]

    # Sort by date
    by_date = sort_tests([t1, t2, t3], sort_by="date")
    assert [t.distributionId for t in by_date] == [50, 100, 200]

def test_filter_tests():
    from kirihara.utils import filter_tests
    from kirihara.models import TestItem

    t_completed = TestItem(distributionId=100, title="Test1", bookName="B1", status=3)
    t_upcoming = TestItem(distributionId=200, title="Test2", bookName="B2", startAt="2099-01-01T00:00:00.000Z", endAt="2099-01-02T00:00:00.000Z", status=None)
    t_expired = TestItem(distributionId=300, title="Test3", bookName="B3", startAt="2020-01-01T00:00:00.000Z", endAt="2020-01-02T00:00:00.000Z", status=None)

    tests = [t_completed, t_upcoming, t_expired]
    assert len(filter_tests(tests, "all")) == 3
    assert [t.distributionId for t in filter_tests(tests, "completed")] == [100]
    assert [t.distributionId for t in filter_tests(tests, "upcoming")] == [200]
    assert [t.distributionId for t in filter_tests(tests, "expired")] == [300]

def test_calculate_human_delay():
    from kirihara.utils import calculate_human_delay
    from kirihara.models import TestQuestionSet, MainQuestion, Question, Option

    # Question set with 2 choice questions and 1 ordering question
    q1 = Question(id=1, text="Q1", options=[Option(id=1, text="A")])
    q2 = Question(id=2, text="Q2", options=[Option(id=2, text="B")])
    mq1 = MainQuestion(id=1, type=0, text="Choice", questions=[q1, q2])

    q3 = Question(id=3, text="Q3", options=[Option(id=3, text="C")])
    mq2 = MainQuestion(id=2, type=1, text="Ordering", questions=[q3])

    q_set = TestQuestionSet(id=1, title="T", bookName="B", count=3, mainQuestions=[mq1, mq2])

    delay = calculate_human_delay(q_set, speed_factor=1.0)
    # 2 choice (4-7.5 each) + 1 ordering (9-18) -> min 17, max 33
    assert 15.0 <= delay <= 36.0

    # 2x speed
    delay_fast = calculate_human_delay(q_set, speed_factor=2.0)
    assert delay_fast < delay

def test_simulate_human_delay_countdown():
    from kirihara.utils import simulate_human_delay_countdown
    # Short duration
    elapsed = simulate_human_delay_countdown(0.1, show_progress=False)
    assert elapsed >= 0.08


