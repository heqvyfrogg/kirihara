import argparse
import sys
import os
import time
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv
from kirihara.client import KiriharaClient
from kirihara.solver import KiriharaSolver
from kirihara.utils import (
    simulate_delay, parse_iso_datetime,
    format_jst, get_test_availability, JST,
    pad_text, get_display_width
)

load_dotenv()

def parse_args(args: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="桐原書店「きりはらの森の学校」自動テスト受験ツール (Kirihara Auto Tester)")
    parser.add_argument("--account", type=str, default=None, help="桐原書店 生徒アカウント名 / ID")
    parser.add_argument("--password", type=str, default=None, help="桐原書店 パスワード")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # login command
    subparsers.add_parser("login", help="ログイン動作を検証し、生徒名・クラス情報を表示")

    # list command
    list_p = subparsers.add_parser("list", help="配信中のテスト一覧と受験可能ステータスを表示")
    list_p.add_argument("--year", type=int, default=2026, help="対象年度 (デフォルト: 2026)")

    # info command
    info_p = subparsers.add_parser("info", help="指定したテストの詳細情報（期間・出題形式）を表示")
    info_p.add_argument("distribution_id", type=int, help="テスト配信ID (distributionId)")

    # run command
    run_p = subparsers.add_parser("run", help="テストを自動解答・提出")
    run_p.add_argument("distribution_id", type=int, help="テスト配信ID (distributionId)")
    run_p.add_argument("--dry-run", action="store_true", help="サーバーへ送信せず、AIが導出した解答プレビューのみ表示")
    run_p.add_argument("--human-like", action="store_true", help="人間らしい思考時間を模倣して待機")
    run_p.add_argument("--target-accuracy", type=float, default=100.0, help="目標正答率（例: 90 で意図的に数問間違える）")
    run_p.add_argument("--wait", action="store_true", help="テスト開始前の場合、開始時刻まで待機して自動開始")

    return parser.parse_args(args)

def get_auth_credentials(args):
    account = args.account or os.environ.get("KIRIHARA_ACCOUNT_NAME") or os.environ.get("ACCOUNT_NAME")
    password = args.password or os.environ.get("KIRIHARA_PASSWORD") or os.environ.get("PASSWORD")
    session_cookie = os.environ.get("SESSION_COOKIE", "")
    return account, password, session_cookie

def run_cli(args_list: Optional[List[str]] = None):
    args = parse_args(args_list)
    account, password, session_cookie = get_auth_credentials(args)
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    client = KiriharaClient(session_cookie=session_cookie)

    if args.command == "login":
        print("[*] 桐原書店サーバーへ認証中...")
        try:
            user = client.ensure_authenticated(account, password) or {}
            info = user.get("userInfo") or {}
            print(f"[+] 認証成功！")
            if info:
                name = info.get("name") or "(未設定)"
                acc = info.get("accountName") or account or "(未設定)"
                s_num = info.get("studentNum") or "(未設定)"
                pref = info.get("placeName") or "(未設定)"
                print(f"    氏名: {name}")
                print(f"    アカウント: {acc}")
                print(f"    出席番号: {s_num}")
                print(f"    都道府県: {pref}")
            else:
                print(f"    User Type: {user.get('userType', '生徒')}")
            for code in (user.get("accessCodes") or []):
                if isinstance(code, dict):
                    print(f"    所属クラス: {code.get('className')} ({code.get('schoolName')})")
        except Exception as e:
            print(f"[!] ログイン失敗: {e}")
            sys.exit(1)

    elif args.command == "list":
        try:
            user = client.ensure_authenticated(account, password) or {}
            info = user.get("userInfo") or {}
            user_name = info.get("name") or "生徒"
            print(f"[+] ログイン中: {user_name} さん")
        except Exception as e:
            print(f"[!] 認証警告: {e}")

        print(f"[*] {args.year}年度の配信テスト一覧を取得中...")
        tests = client.get_tests(year=args.year)
        print(f"\n=== {args.year}年度 配信テスト一覧（全 {len(tests)} 件） ===")
        
        h_id = pad_text("ID", 7)
        h_status = pad_text("ステータス", 18)
        h_score = pad_text("得点", 8, align="center")
        h_window = pad_text("実施期間 (JST)", 28)
        h_title = pad_text("テスト名", 30)
        h_book = "対象書籍"
        
        print(f"{h_id} | {h_status} | {h_score} | {h_window} | {h_title} | {h_book}")
        print("-" * 125)
        for t in tests:
            status_label, time_hint, is_open = get_test_availability(t.startAt, t.endAt, t.status)
            score_str = f"{t.correctCount}/{t.questionCount}" if t.correctCount is not None else "-"
            start_fmt = format_jst(parse_iso_datetime(t.startAt))
            end_fmt = format_jst(parse_iso_datetime(t.endAt))
            window_str = f"{start_fmt} ～ {end_fmt}" if start_fmt != "-" else "-"
            
            c_id = pad_text(t.distributionId, 7)
            c_status = pad_text(status_label, 18)
            c_score = pad_text(score_str, 8, align="center")
            c_window = pad_text(window_str, 28)
            c_title = pad_text(t.title, 30)
            c_book = t.bookName
            print(f"{c_id} | {c_status} | {c_score} | {c_window} | {c_title} | {c_book}")

    elif args.command == "info":
        try:
            client.ensure_authenticated(account, password)
        except Exception as e:
            print(f"[!] 認証エラー: {e}")
            sys.exit(1)

        print(f"[*] テスト配信ID {args.distribution_id} の詳細情報を取得中...")
        tests = client.get_tests(year=2026)
        matched_test = next((t for t in tests if t.distributionId == args.distribution_id), None)

        url_info = client.get_test_url(args.distribution_id)
        json_url = url_info.get("jsonUrl")
        q_set = client.fetch_question_set(json_url) if json_url else None

        print(f"\n=== テスト詳細情報 (ID: {args.distribution_id}) ===")
        title = matched_test.title if matched_test else q_set.title if q_set else "-"
        book = matched_test.bookName if matched_test else q_set.bookName if q_set else "-"
        print(f"タイトル  : {title}")
        print(f"対象書籍  : {book}")
        print(f"問題数    : {q_set.count if q_set else (matched_test.questionCount if matched_test else '-')} 問")
        if matched_test:
            status_label, time_hint, is_open = get_test_availability(matched_test.startAt, matched_test.endAt, matched_test.status)
            start_fmt = format_jst(parse_iso_datetime(matched_test.startAt))
            end_fmt = format_jst(parse_iso_datetime(matched_test.endAt))
            print(f"実施期間  : {start_fmt} ～ {end_fmt} JST ({time_hint})")
            print(f"ステータス: {status_label}")
            if matched_test.correctCount is not None:
                print(f"過去スコア: {matched_test.correctCount} / {matched_test.questionCount} 点")

        if q_set:
            print("\n--- 大問構成 ---")
            for idx, mq in enumerate(q_set.mainQuestions, 1):
                type_name = "語順整序 (並び替え)" if mq.type == 1 else "選択問題"
                print(f"  大問{idx} [{type_name}] ({len(mq.questions)}問): {mq.text}")

    elif args.command == "run":
        try:
            client.ensure_authenticated(account, password)
        except Exception as e:
            print(f"[!] 認証エラー: {e}")
            sys.exit(1)

        tests = client.get_tests(year=2026)
        matched_test = next((t for t in tests if t.distributionId == args.distribution_id), None)

        if matched_test and not args.dry_run:
            status_label, time_hint, is_open = get_test_availability(
                matched_test.startAt, matched_test.endAt, matched_test.status
            )
            if matched_test.status == 3:
                print(f"[!] 注意: このテスト (ID: {args.distribution_id}) は既に受験完了しています (得点: {matched_test.correctCount}/{matched_test.questionCount})。")
            elif not is_open:
                start_dt = parse_iso_datetime(matched_test.startAt)
                now = datetime.now(JST)
                if start_dt and now < start_dt:
                    diff_sec = (start_dt - now).total_seconds()
                    print(f"[!] このテストはまだ開始されていません。")
                    print(f"    開始日時: {format_jst(start_dt)} JST ({time_hint})")
                    if args.wait:
                        print(f"[*] --wait が指定されたため、開始時刻まで待機します ({int(diff_sec)} 秒待機)...")
                        time.sleep(diff_sec + 2)  # +2s buffer
                        print("[+] 開始時刻に到達しました。受験を開始します。")
                    else:
                        print("[!] 待機して自動開始したい場合は `--wait` オプションを付けて実行してください。")
                        print("[!] 解答プレビューのみ確認したい場合は `--dry-run` を付けて実行してください。")
                        sys.exit(0)

        print(f"[*] テスト配信ID {args.distribution_id} の問題データを取得中...")
        url_info = client.get_test_url(args.distribution_id)
        json_url = url_info.get("jsonUrl")
        if not json_url:
            print(f"[!] エラー: 問題JSONのURL取得に失敗しました。")
            sys.exit(1)

        q_set = client.fetch_question_set(json_url)
        print(f"[+] 問題取得完了: 『{q_set.bookName}』 {q_set.title} (全{q_set.count}問)")

        if not args.dry_run:
            print("[*] サーバー側テスト開始状態を同期中...")
            client.sync_start_answer(args.distribution_id)

        solver = KiriharaSolver(api_key=gemini_key)
        accuracy_ratio = args.target_accuracy / 100.0
        print(f"[*] AI自動解答エンジン（Geminiバッチ推論）を実行中 (目標正答率: {args.target_accuracy}%)...")
        payload = solver.solve_test(args.distribution_id, q_set, target_accuracy=accuracy_ratio)

        print("\n=== AI解答プレビュー ===")
        preview_lines = solver.format_preview(q_set, payload)
        for line in preview_lines:
            print(line)

        if args.dry_run:
            print("\n[!] ドライランモードのため、サーバーへの提出は行いませんでした。")
            return

        if args.human_like:
            print("\n[*] 人間らしい解答間隔をシミュレート中...")
            simulate_delay(3.0, 6.0)

        print("\n[*] 解答を桐原書店サーバーへ一括送信中...")
        client.submit_answers(payload)
        print("[+] 送信・採点が完了しました！")

        # Verify score
        try:
            latest_tests = client.get_tests(year=2026)
            for t in latest_tests:
                if t.distributionId == args.distribution_id:
                    print(f"\n🏆 受験結果: {t.title} -> 正解数: {t.correctCount}/{t.questionCount} 点 (ステータス: 完了)")
                    break
        except Exception:
            pass
