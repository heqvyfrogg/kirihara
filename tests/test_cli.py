# tests/test_cli.py
from kirihara.cli import parse_args, get_auth_credentials

def test_parse_args():
    args = parse_args(["list", "--year", "2026"])
    assert args.command == "list"
    assert args.year == 2026

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

    args_human = parse_args(["run", "94506", "--human-like"])
    assert args_human.human_like is True

def test_get_auth_credentials(monkeypatch):
    monkeypatch.setenv("KIRIHARA_ACCOUNT_NAME", "env_user")
    monkeypatch.setenv("KIRIHARA_PASSWORD", "env_pass")
    monkeypatch.setenv("SESSION_COOKIE", "env_cookie")

    args = parse_args(["list"])
    account, password, cookie = get_auth_credentials(args)
    assert account == "env_user"
    assert password == "env_pass"
    assert cookie == "env_cookie"
