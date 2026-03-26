"""
Claude APIを使って、メール本文から取引情報を抽出するモジュール
"""
import json
import re
from typing import List, Dict, Optional
import anthropic


EXTRACTION_SYSTEM_PROMPT = """あなたは家計簿の専門家です。
メールの本文から決済・入出金情報を抽出してJSON形式で返してください。

抽出するフィールド:
- date: 取引日 (YYYY-MM-DD形式。不明な場合はメール送信日を使用)
- amount: 金額 (整数、円単位。支出はマイナス、収入はプラス)
- category: カテゴリ（以下から選択）
  支出: 食費, 日用品, 交通費, 娯楽・趣味, 通信費, 光熱費, 医療費, 保険, 住居費, 教育費, 被服費, 美容・理容, サブスクリプション, ネットショッピング, その他支出
  収入: 給与, 賞与, 副収入, 投資収益, その他収入
- description: 取引の説明（店名・サービス名・商品名など30文字以内）
- payment_method: 支払い方法（クレジットカード, デビットカード, 電子マネー, 銀行振込, 口座引き落とし, 現金, 不明）

返却形式（JSONのみ、説明文は不要）:
{"transactions": [{"date": "...", "amount": -1000, "category": "...", "description": "...", "payment_method": "..."}]}

取引情報が見つからない場合:
{"transactions": []}

重要:
- 1つのメールに複数の取引が含まれる場合はすべて抽出する
- 金額は必ず整数にする（小数点なし）
- 確実でない情報は含めない"""


def parse_date_from_email(date_str: str) -> str:
    """メールのDateヘッダーをYYYY-MM-DD形式に変換する"""
    import email.utils
    try:
        parsed = email.utils.parsedate_tz(date_str)
        if parsed:
            dt = email.utils.mktime_tz(parsed)
            from datetime import datetime, timezone
            d = datetime.fromtimestamp(dt, tz=timezone.utc)
            return d.strftime("%Y-%m-%d")
    except Exception:
        pass
    return ""


def extract_transactions_from_email(
    client: anthropic.Anthropic,
    email_data: Dict,
) -> List[Dict]:
    """
    1件のメールから取引情報を抽出する

    Returns:
        List of transaction dicts
    """
    email_date = parse_date_from_email(email_data.get("date", ""))

    user_message = f"""以下のメールから取引情報を抽出してください。

送信日: {email_date}
差出人: {email_data.get('sender', '')}
件名: {email_data.get('subject', '')}

本文:
{email_data.get('body', '')}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        content = response.content[0].text.strip()

        # JSON部分を抽出（余分なテキストがある場合に対応）
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()

        data = json.loads(content)
        transactions = data.get("transactions", [])

        # メールのメタ情報を付加
        for tx in transactions:
            tx["source_account"] = email_data.get("account", "")
            tx["source_subject"] = email_data.get("subject", "")
            # dateが空の場合はメール送信日を使用
            if not tx.get("date") and email_date:
                tx["date"] = email_date

        return transactions

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  抽出エラー ({email_data.get('subject', '')[:30]}): {e}")
        return []


def extract_all_transactions(
    api_key: str,
    emails: List[Dict],
) -> List[Dict]:
    """
    複数のメールから取引情報をまとめて抽出する

    Args:
        api_key: Anthropic APIキー
        emails: email_fetcher.pyが返すメールリスト

    Returns:
        取引情報のリスト（dateでソート済み）
    """
    client = anthropic.Anthropic(api_key=api_key)
    all_transactions = []

    print(f"\n取引情報を抽出中... (合計{len(emails)}件のメール)")

    for i, email_data in enumerate(emails, 1):
        subject = email_data.get("subject", "")[:40]
        print(f"  [{i}/{len(emails)}] {subject}")

        transactions = extract_transactions_from_email(client, email_data)
        all_transactions.extend(transactions)

    # 日付でソート
    all_transactions.sort(key=lambda x: x.get("date", ""))

    print(f"\n抽出完了: {len(all_transactions)}件の取引を検出")
    return all_transactions
