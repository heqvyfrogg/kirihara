# tests/test_cli.py
from kirihara.cli import parse_args, get_auth_credentials

def test_parse_args():
    args_list = parse_args(["list", "--year", "2026", "--sort", "status", "--reverse", "--filter-status", "active"])
    assert args_list.command == "list"
    assert args_list.year == 2026
    assert args_list.sort == "status"
    assert args_list.reverse is True
    assert args_list.filter_status == "active"

    args_info = parse_args(["info", "94506"])
    assert args_info.command == "info"
    assert args_info.distribution_id == 94506

    args_login = parse_args(["--account", "myuser", "--password", "mypw", "login"])
    assert args_login.command == "login"
    assert args_login.account == "myuser"
    assert args_login.password == "mypw"

    args_run = parse_args(["run", "94506", "--dry-run", "--target-accuracy", "90", "--wait"])
    assert args_run.command == "run"
    assert args_run.distribution_id == 94506
    assert args_run.dry_run is True
    assert args_run.target_accuracy == 90.0
    assert args_run.wait is True
    assert args_run.human_like is False

    args_human = parse_args(["run", "94506", "--human-like", "--speed", "1.5", "--delay-sec", "45", "--instant", "--model", "gemini-3.5-flash"])
    assert args_human.human_like is True
    assert args_human.speed == 1.5
    assert args_human.delay_sec == 45.0
    assert args_human.instant is True
    args_clear = parse_args(["clear-cache"])
    assert args_clear.command == "clear-cache"

def test_get_auth_credentials(monkeypatch):
    monkeypatch.setenv("KIRIHARA_ACCOUNT_NAME", "env_user")
    monkeypatch.setenv("KIRIHARA_PASSWORD", "env_pass")
    monkeypatch.setenv("SESSION_COOKIE", "env_cookie")

    args = parse_args(["list"])
    account, password, cookie = get_auth_credentials(args)
    assert account == "env_user"
    assert password == "env_pass"
    assert cookie == "env_cookie"
