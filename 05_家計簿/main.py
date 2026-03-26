#!/usr/bin/env python3
"""
メールから家計簿を自動生成するメインスクリプト

使い方:
  1. .env.example を .env にコピーして認証情報を設定
  2. pip install -r requirements.txt
  3. python main.py

オプション:
  python main.py --days 60      # 過去60日分を取得（デフォルト: 30日）
  python main.py --output ./out # 出力先ディレクトリを指定
"""
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# .envファイルの読み込み
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    print("注意: python-dotenv が未インストールです。環境変数を直接設定してください。")

from email_fetcher import fetch_all_financial_emails
from transaction_extractor import extract_all_transactions
from budget_generator import generate_budget_report


def get_config() -> dict:
    """環境変数から設定を取得する"""
    config = {
        "accounts": [],
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "days": int(os.getenv("EMAIL_FETCH_DAYS", "30")),
        "output_dir": os.getenv("OUTPUT_DIR", "./output"),
    }

    # Gmailアカウント設定
    for i in range(1, 10):
        email_key = f"GMAIL_ACCOUNT_{i}_EMAIL"
        password_key = f"GMAIL_ACCOUNT_{i}_PASSWORD"
        email_val = os.getenv(email_key, "")
        password_val = os.getenv(password_key, "")
        if email_val and password_val:
            config["accounts"].append({
                "email": email_val,
                "password": password_val,
            })
        else:
            break

    return config


def validate_config(config: dict) -> list[str]:
    """設定の検証。エラーメッセージのリストを返す"""
    errors = []
    if not config["accounts"]:
        errors.append(
            "Gmailアカウントが設定されていません。\n"
            ".envファイルで GMAIL_ACCOUNT_1_EMAIL と GMAIL_ACCOUNT_1_PASSWORD を設定してください。"
        )
    if not config["api_key"]:
        errors.append(
            "Anthropic APIキーが設定されていません。\n"
            ".envファイルで ANTHROPIC_API_KEY を設定してください。"
        )
    return errors


def main():
    parser = argparse.ArgumentParser(description="メールから家計簿を自動生成")
    parser.add_argument("--days", type=int, help="取得する過去の日数（デフォルト: .envの設定）")
    parser.add_argument("--output", type=str, help="出力ディレクトリ（デフォルト: .envの設定）")
    args = parser.parse_args()

    print("=" * 60)
    print("  メール家計簿ジェネレーター")
    print("=" * 60)

    # 設定取得
    config = get_config()
    if args.days:
        config["days"] = args.days
    if args.output:
        config["output_dir"] = args.output

    # 出力先をスクリプトからの相対パスに解決
    script_dir = Path(__file__).parent
    output_dir = Path(config["output_dir"])
    if not output_dir.is_absolute():
        output_dir = script_dir / output_dir
    config["output_dir"] = str(output_dir)

    # 設定検証
    errors = validate_config(config)
    if errors:
        print("\n設定エラー:")
        for err in errors:
            print(f"  ✗ {err}")
        print(f"\n.env.example を参考に {script_dir}/.env を作成してください。")
        sys.exit(1)

    # 設定表示
    account_list = [a["email"] for a in config["accounts"]]
    since_date = datetime.now() - timedelta(days=config["days"])
    print(f"\n対象アカウント: {', '.join(account_list)}")
    print(f"取得期間: {since_date.strftime('%Y年%m月%d日')} 〜 今日")
    print(f"出力先: {config['output_dir']}")

    # STEP 1: メール取得
    print("\n[STEP 1] メールを取得中...")
    emails = fetch_all_financial_emails(config["accounts"], days=config["days"])

    if not emails:
        print("\n金融関連メールが見つかりませんでした。")
        print("ヒント: キーワードが一致するメールがINBOXにあるか確認してください。")
        # 空のレポートを生成
        report_path = generate_budget_report(
            [],
            output_dir=config["output_dir"],
            report_period=f"{since_date.strftime('%Y年%m月%d日')}〜{datetime.now().strftime('%Y年%m月%d日')}",
        )
        print(f"\n空のレポートを生成しました: {report_path}")
        return

    print(f"\n合計 {len(emails)} 件の金融関連メールを取得しました。")

    # STEP 2: 取引情報の抽出
    print("\n[STEP 2] Claude APIで取引情報を抽出中...")
    transactions = extract_all_transactions(config["api_key"], emails)

    # STEP 3: レポート生成
    print("\n[STEP 3] 家計簿レポートを生成中...")
    period = f"{since_date.strftime('%Y年%m月%d日')}〜{datetime.now().strftime('%Y年%m月%d日')}"
    report_path = generate_budget_report(
        transactions,
        output_dir=config["output_dir"],
        report_period=period,
    )

    print("\n" + "=" * 60)
    print("  完了！")
    print("=" * 60)
    print(f"\nレポートファイル: {report_path}")
    print(f"取引件数: {len(transactions)} 件")

    # サマリー表示
    total_income = sum(tx["amount"] for tx in transactions if tx.get("amount", 0) > 0)
    total_expense = sum(abs(tx["amount"]) for tx in transactions if tx.get("amount", 0) < 0)
    balance = total_income - total_expense
    print(f"\n収入合計: ¥{total_income:,}")
    print(f"支出合計: ¥{total_expense:,}")
    print(f"収  支:  {'▲' if balance < 0 else '+'}¥{abs(balance):,}")


if __name__ == "__main__":
    main()
