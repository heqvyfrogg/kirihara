import hashlib
import re
import time
import random
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Any

JST = timezone(timedelta(hours=9))

def hash_password(password: str) -> str:
    """Hash password with SHA-256 and return lowercase hex string."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().lower()

def clean_html(text: Optional[str]) -> str:
    """Remove HTML tags like <br>, <u>, </u>, etc."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def simulate_delay(min_sec: float = 1.0, max_sec: float = 3.0) -> float:
    """Simulate human reading/answering delay and return the elapsed seconds."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay

def get_display_width(text: str) -> int:
    """Calculate terminal display width considering full-width characters and emojis."""
    width = 0
    for char in str(text):
        w = unicodedata.east_asian_width(char)
        if w in ('F', 'W'):
            width += 2
        elif ord(char) >= 0x1F000 or char in ('🔥', '🏆', '👉', '【', '】', '（', '）', '～', '・'):
            width += 2
        else:
            width += 1
    return width

def pad_text(text: Any, target_width: int, align: str = "left") -> str:
    """Pad string with spaces to reach exact terminal display width."""
    text_str = str(text) if text is not None else "-"
    cur_width = get_display_width(text_str)
    if cur_width >= target_width:
        return text_str
    padding = " " * (target_width - cur_width)
    if align == "right":
        return padding + text_str
    elif align == "center":
        left_pad = " " * ((target_width - cur_width) // 2)
        right_pad = " " * (target_width - cur_width - len(left_pad))
        return left_pad + text_str + right_pad
    return text_str + padding

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO8601 string to timezone-aware datetime."""
    if not dt_str:
        return None
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        return dt.astimezone(JST)
    except Exception:
        return None

def format_jst(dt: Optional[datetime]) -> str:
    """Format datetime to JST human-readable string (MM/DD HH:MM)."""
    if not dt:
        return "-"
    return dt.strftime("%m/%d %H:%M")

def get_test_availability(
    start_at_str: Optional[str],
    end_at_str: Optional[str],
    status: Optional[int]
) -> Tuple[str, str, bool]:
    """
    Determine test status string, detailed reason, and whether it is currently open for submission.
    Returns: (status_label, detailed_info, is_open)
    """
    now = datetime.now(JST)
    start_dt = parse_iso_datetime(start_at_str)
    end_dt = parse_iso_datetime(end_at_str)

    if status == 3:
        return "完了 (Completed)", "受験済み", False

    if start_dt and now < start_dt:
        diff = start_dt - now
        hours = int(diff.total_seconds() // 3600)
        mins = int((diff.total_seconds() % 3600) // 60)
        time_hint = f"あと {hours}時間{mins}分後 ({format_jst(start_dt)}〜)"
        return "開始前 (Upcoming)", time_hint, False

    if end_dt and now > end_dt:
        return "期限切れ (Expired)", f"{format_jst(end_dt)} に終了", False

    # Within open window
    if end_dt:
        diff = end_dt - now
        hours = int(diff.total_seconds() // 3600)
        mins = int((diff.total_seconds() % 3600) // 60)
        time_hint = f"締切まであと {hours}時間{mins}分 ({format_jst(end_dt)}まで)"
    else:
        time_hint = "期限なし"

    return "受験可能 (Active)", time_hint, True

def get_status_rank(status_label: str) -> int:
    """Assign priority rank for status: Active (1) > Upcoming (2) > Completed (4) > Expired (5) > Other (3)"""
    if "受験可能" in status_label or "Active" in status_label:
        return 1
    elif "開始前" in status_label or "Upcoming" in status_label:
        return 2
    elif "完了" in status_label or "Completed" in status_label:
        return 4
    elif "期限切れ" in status_label or "Expired" in status_label:
        return 5
    return 3

def sort_tests(
    tests: list,
    sort_by: str = "date",
    reverse: bool = False
) -> list:
    """
    Sort a list of TestItem objects.
    sort_by: 'date', 'id', 'status', 'score', 'title', 'book'
    """
    def get_key(t):
        if sort_by == "id":
            return t.distributionId
        elif sort_by == "status":
            label, _, _ = get_test_availability(t.startAt, t.endAt, t.status)
            return (get_status_rank(label), t.distributionId)
        elif sort_by == "score":
            return t.correctCount if t.correctCount is not None else -1
        elif sort_by == "title":
            return str(t.title or "")
        elif sort_by == "book":
            return str(t.bookName or "")
        else:  # 'date' default
            dt = parse_iso_datetime(t.startAt)
            return dt.timestamp() if dt else 0.0

    return sorted(tests, key=get_key, reverse=reverse)

def filter_tests(
    tests: list,
    filter_status: str = "all"
) -> list:
    """
    Filter tests by status: 'all', 'active', 'upcoming', 'completed', 'expired'
    """
    if not filter_status or filter_status == "all":
        return tests

    filtered = []
    for t in tests:
        status_label, _, is_open = get_test_availability(t.startAt, t.endAt, t.status)
        if filter_status == "active" and is_open:
            filtered.append(t)
        elif filter_status == "upcoming" and ("開始前" in status_label or "Upcoming" in status_label):
            filtered.append(t)
        elif filter_status == "completed" and (t.status == 3 or "完了" in status_label):
            filtered.append(t)
        elif filter_status == "expired" and ("期限切れ" in status_label or "Expired" in status_label):
            filtered.append(t)
    return filtered
