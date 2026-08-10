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
