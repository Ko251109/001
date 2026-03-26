"""
Gmail IMAP接続でメールを取得するモジュール
"""
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import os
from typing import List, Dict, Optional


# 金融関連メールを特定するキーワード
FINANCIAL_KEYWORDS = [
    # 決済・支払い
    "決済", "お支払い", "支払い完了", "ご利用",
    "購入完了", "注文確認", "領収", "請求",
    # 入出金
    "入金", "出金", "振込", "引き落とし", "口座",
    # クレジットカード
    "クレジット", "カード利用", "ご利用代金",
    # 銀行・金融機関
    "ご入金", "ご出金", "残高", "明細",
    # ショッピング・EC
    "Amazon", "楽天", "Yahoo", "メルカリ",
    "PayPay", "d払い", "au PAY", "LINE Pay",
    "ApplePay", "GooglePay",
    # 公共料金・固定費
    "電気料金", "ガス料金", "水道料金", "NHK",
    "保険料", "家賃", "管理費",
    # 英語キーワード
    "payment", "receipt", "invoice", "order", "purchase",
    "charged", "billing", "transaction",
]


def decode_mime_header(header: str) -> str:
    """MIMEエンコードされたヘッダーをデコードする"""
    decoded_parts = decode_header(header)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def get_email_body(msg: email.message.Message) -> str:
    """メールの本文を取得する（テキスト部分のみ）"""
    body_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_parts.append(payload.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        body_parts.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body_parts.append(payload.decode(charset, errors="replace"))
            except (LookupError, UnicodeDecodeError):
                body_parts.append(payload.decode("utf-8", errors="replace"))

    return "\n".join(body_parts)


def is_financial_email(subject: str, body: str) -> bool:
    """金融関連メールかどうか判定する"""
    text = (subject + " " + body[:500]).lower()
    for keyword in FINANCIAL_KEYWORDS:
        if keyword.lower() in text:
            return True
    return False


def fetch_emails_from_account(
    email_address: str,
    password: str,
    days: int = 30,
) -> List[Dict]:
    """
    Gmailアカウントからメールを取得する

    Returns:
        List of dicts with keys: account, subject, sender, date, body
    """
    emails = []
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_address, password)
        mail.select("INBOX")

        # 指定期間のメールを検索
        _, message_ids = mail.search(None, f'SINCE "{since_date}"')

        if not message_ids[0]:
            print(f"  [{email_address}] 対象メールなし")
            mail.logout()
            return emails

        ids = message_ids[0].split()
        print(f"  [{email_address}] {len(ids)}件のメールを確認中...")

        for msg_id in ids:
            try:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = decode_mime_header(msg.get("Subject", ""))
                sender = decode_mime_header(msg.get("From", ""))
                date_str = msg.get("Date", "")
                body = get_email_body(msg)

                if is_financial_email(subject, body):
                    # 本文は最大3000文字に制限（API節約）
                    emails.append({
                        "account": email_address,
                        "subject": subject,
                        "sender": sender,
                        "date": date_str,
                        "body": body[:3000],
                    })

            except Exception as e:
                print(f"  メール解析エラー (ID: {msg_id}): {e}")
                continue

        mail.logout()
        print(f"  [{email_address}] 金融関連メール: {len(emails)}件")

    except imaplib.IMAP4.error as e:
        raise ConnectionError(
            f"Gmail接続エラー ({email_address}): {e}\n"
            "アプリパスワードを使用しているか確認してください。\n"
            "設定: https://myaccount.google.com/apppasswords"
        )

    return emails


def fetch_all_financial_emails(
    accounts: List[Dict[str, str]],
    days: int = 30,
) -> List[Dict]:
    """
    複数のGmailアカウントから金融関連メールをまとめて取得する

    Args:
        accounts: [{"email": "...", "password": "..."}, ...]
        days: 何日前まで遡るか
    """
    all_emails = []
    for account in accounts:
        print(f"\nアカウント取得中: {account['email']}")
        emails = fetch_emails_from_account(
            account["email"],
            account["password"],
            days=days,
        )
        all_emails.extend(emails)

    return all_emails
