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

def simulate_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """Simulate human reading/answering delay."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

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

    return "🔥受験可能 (Active)", time_hint, True
