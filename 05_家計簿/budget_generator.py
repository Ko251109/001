"""
取引情報からMarkdown形式の家計簿レポートを生成するモジュール
"""
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple
import os


# カテゴリの表示順序
EXPENSE_CATEGORIES = [
    "食費", "日用品", "交通費", "娯楽・趣味", "通信費",
    "光熱費", "医療費", "保険", "住居費", "教育費",
    "被服費", "美容・理容", "サブスクリプション", "ネットショッピング", "その他支出",
]
INCOME_CATEGORIES = ["給与", "賞与", "副収入", "投資収益", "その他収入"]


def format_amount(amount: int) -> str:
    """金額を日本円形式でフォーマット"""
    return f"¥{abs(amount):,}"


def summarize_by_category(transactions: List[Dict]) -> Tuple[Dict, Dict]:
    """カテゴリ別に集計する"""
    income_by_cat = defaultdict(int)
    expense_by_cat = defaultdict(int)

    for tx in transactions:
        amount = tx.get("amount", 0)
        category = tx.get("category", "その他支出")
        if amount > 0:
            income_by_cat[category] += amount
        else:
            expense_by_cat[category] += abs(amount)

    return dict(income_by_cat), dict(expense_by_cat)


def summarize_by_month(transactions: List[Dict]) -> Dict[str, List[Dict]]:
    """月別にグループ化する"""
    by_month = defaultdict(list)
    for tx in transactions:
        date = tx.get("date", "")
        if date:
            month_key = date[:7]  # YYYY-MM
        else:
            month_key = "日付不明"
        by_month[month_key].append(tx)
    return dict(sorted(by_month.items()))


def generate_category_bar(amount: int, max_amount: int, width: int = 20) -> str:
    """カテゴリ金額のバーを生成"""
    if max_amount == 0:
        return ""
    filled = int((amount / max_amount) * width)
    return "█" * filled + "░" * (width - filled)


def generate_monthly_section(month_key: str, transactions: List[Dict]) -> str:
    """月別セクションのMarkdownを生成"""
    lines = []

    # 月の表示
    if month_key != "日付不明":
        year, month = month_key.split("-")
        lines.append(f"\n## {year}年{int(month)}月\n")
    else:
        lines.append("\n## 日付不明\n")

    # 月の集計
    total_income = sum(tx["amount"] for tx in transactions if tx.get("amount", 0) > 0)
    total_expense = sum(abs(tx["amount"]) for tx in transactions if tx.get("amount", 0) < 0)
    balance = total_income - total_expense

    income_by_cat, expense_by_cat = summarize_by_category(transactions)

    # サマリーカード
    lines.append("### 月次サマリー\n")
    lines.append("| 項目 | 金額 |")
    lines.append("|------|------|")
    lines.append(f"| 収入合計 | **{format_amount(total_income)}** |")
    lines.append(f"| 支出合計 | **{format_amount(total_expense)}** |")
    balance_str = f"{'▲' if balance < 0 else '+'}{format_amount(abs(balance))}"
    lines.append(f"| 収支 | **{balance_str}** |")
    lines.append("")

    # 収入カテゴリ別
    if income_by_cat:
        lines.append("### 収入内訳\n")
        lines.append("| カテゴリ | 金額 |")
        lines.append("|----------|------|")
        for cat in INCOME_CATEGORIES:
            if cat in income_by_cat:
                lines.append(f"| {cat} | {format_amount(income_by_cat[cat])} |")
        for cat, amount in income_by_cat.items():
            if cat not in INCOME_CATEGORIES:
                lines.append(f"| {cat} | {format_amount(amount)} |")
        lines.append("")

    # 支出カテゴリ別
    if expense_by_cat:
        lines.append("### 支出内訳\n")
        max_expense = max(expense_by_cat.values()) if expense_by_cat else 1
        lines.append("| カテゴリ | 金額 | 割合 |")
        lines.append("|----------|------|------|")
        sorted_expenses = sorted(expense_by_cat.items(), key=lambda x: x[1], reverse=True)
        for cat, amount in sorted_expenses:
            ratio = (amount / total_expense * 100) if total_expense > 0 else 0
            lines.append(f"| {cat} | {format_amount(amount)} | {ratio:.1f}% |")
        lines.append("")

    # 取引明細
    lines.append("### 取引明細\n")
    lines.append("| 日付 | 区分 | カテゴリ | 内容 | 支払方法 | 金額 |")
    lines.append("|------|------|----------|------|----------|------|")

    for tx in sorted(transactions, key=lambda x: x.get("date", "")):
        date = tx.get("date", "-")
        amount = tx.get("amount", 0)
        category = tx.get("category", "-")
        description = tx.get("description", "-")
        payment_method = tx.get("payment_method", "-")
        account = tx.get("source_account", "")

        if amount > 0:
            kind = "収入"
            amount_str = f"+{format_amount(amount)}"
        else:
            kind = "支出"
            amount_str = f"-{format_amount(abs(amount))}"

        # アカウント略称
        account_short = account.split("@")[0][:10] if account else ""
        desc_with_account = f"{description}" + (f" ({account_short})" if account_short else "")

        lines.append(
            f"| {date} | {kind} | {category} | {desc_with_account} | {payment_method} | {amount_str} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_annual_summary(transactions: List[Dict], year: str = None) -> str:
    """年間サマリーのMarkdownを生成"""
    if year:
        transactions = [tx for tx in transactions if tx.get("date", "").startswith(year)]

    total_income = sum(tx["amount"] for tx in transactions if tx.get("amount", 0) > 0)
    total_expense = sum(abs(tx["amount"]) for tx in transactions if tx.get("amount", 0) < 0)
    balance = total_income - total_expense

    income_by_cat, expense_by_cat = summarize_by_category(transactions)

    lines = []
    if year:
        lines.append(f"# {year}年 家計簿サマリー\n")
    else:
        lines.append("# 家計簿サマリー\n")

    lines.append("## 年間収支\n")
    lines.append("| 項目 | 金額 |")
    lines.append("|------|------|")
    lines.append(f"| 総収入 | **{format_amount(total_income)}** |")
    lines.append(f"| 総支出 | **{format_amount(total_expense)}** |")
    balance_str = f"{'▲' if balance < 0 else '+'}{format_amount(abs(balance))}"
    lines.append(f"| 年間収支 | **{balance_str}** |")
    lines.append("")

    # 支出カテゴリ別ランキング
    if expense_by_cat:
        lines.append("## 支出カテゴリ別集計\n")
        max_expense = max(expense_by_cat.values()) if expense_by_cat else 1
        sorted_expenses = sorted(expense_by_cat.items(), key=lambda x: x[1], reverse=True)
        lines.append("| カテゴリ | 金額 | 割合 | グラフ |")
        lines.append("|----------|------|------|--------|")
        for cat, amount in sorted_expenses:
            ratio = (amount / total_expense * 100) if total_expense > 0 else 0
            bar = generate_category_bar(amount, max_expense)
            lines.append(f"| {cat} | {format_amount(amount)} | {ratio:.1f}% | {bar} |")
        lines.append("")

    return "\n".join(lines)


def generate_budget_report(
    transactions: List[Dict],
    output_dir: str = "./output",
    report_period: str = None,
) -> str:
    """
    家計簿レポートを生成してMarkdownファイルに保存する

    Args:
        transactions: 取引情報のリスト
        output_dir: 出力ディレクトリ
        report_period: レポート期間の説明（例: "2026年1月〜3月"）

    Returns:
        生成されたファイルのパス
    """
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now()
    filename = f"家計簿_{now.strftime('%Y%m%d_%H%M%S')}.md"
    filepath = os.path.join(output_dir, filename)

    lines = []

    # ヘッダー
    lines.append("# 家計簿レポート\n")
    lines.append(f"生成日時: {now.strftime('%Y年%m月%d日 %H:%M')}")
    if report_period:
        lines.append(f"対象期間: {report_period}")
    lines.append(f"取引件数: {len(transactions)}件")
    lines.append("")

    if not transactions:
        lines.append("> 取引情報が見つかりませんでした。")
        content = "\n".join(lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    # 年を特定
    years = sorted(set(tx.get("date", "")[:4] for tx in transactions if tx.get("date")))

    # 年間サマリー
    for year in years:
        lines.append(generate_annual_summary(transactions, year))

    # 月別詳細
    lines.append("---\n")
    lines.append("# 月別詳細\n")

    by_month = summarize_by_month(transactions)
    for month_key, month_transactions in by_month.items():
        lines.append(generate_monthly_section(month_key, month_transactions))

    # フッター
    lines.append("---\n")
    lines.append(f"*このレポートはメールの決済・入出金情報を自動集計したものです。*")
    lines.append(f"*生成: {now.strftime('%Y-%m-%d %H:%M:%S')}*")

    content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nレポートを保存しました: {filepath}")
    return filepath
