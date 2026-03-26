# メール家計簿ジェネレーター

GmailのINBOXから決済・入出金メールを自動取得し、Claude APIで取引情報を抽出して家計簿レポート（Markdown）を生成するツールです。

## 機能

- 複数のGmailアカウントに対応（IMAP接続）
- Claude Haiku APIで取引情報を自動解析
- 月別・カテゴリ別の集計
- Markdown形式のレポート出力

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd 05_家計簿
pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env`ファイルを編集して以下を設定:

```env
GMAIL_ACCOUNT_1_EMAIL=your_email1@gmail.com
GMAIL_ACCOUNT_1_PASSWORD=アプリパスワード

GMAIL_ACCOUNT_2_EMAIL=your_email2@gmail.com
GMAIL_ACCOUNT_2_PASSWORD=アプリパスワード

ANTHROPIC_API_KEY=sk-ant-...
EMAIL_FETCH_DAYS=30
```

### Gmailアプリパスワードの取得方法

1. Googleアカウント → セキュリティ → 2段階認証を有効化
2. セキュリティ → アプリパスワード → 新しいアプリパスワードを作成
3. 生成された16桁のパスワードを `.env` に設定

## 使い方

```bash
# 基本的な使い方（過去30日分）
python main.py

# 過去60日分を取得
python main.py --days 60

# 出力先を指定
python main.py --output ./reports
```

## 出力形式

`output/` ディレクトリに `家計簿_YYYYMMDD_HHMMSS.md` が生成されます。

### レポート構成

```
# 家計簿レポート
生成日時・対象期間・取引件数

# YYYY年 家計簿サマリー
  - 年間収支（収入・支出・収支）
  - 支出カテゴリ別集計（割合・バーグラフ）

# 月別詳細
  ## YYYY年MM月
    ### 月次サマリー（収入・支出・収支）
    ### 収入内訳
    ### 支出内訳（割合付き）
    ### 取引明細（日付・区分・カテゴリ・内容・支払方法・金額）
```

## 対応メール種別

| 種別 | 例 |
|------|-----|
| クレジットカード | カード利用通知、利用明細 |
| 電子マネー | PayPay、楽天Pay、d払い |
| ECサイト | Amazon、楽天市場、Yahoo!ショッピング |
| 銀行 | 振込通知、入出金通知 |
| 公共料金 | 電気・ガス・水道料金 |
| サブスクリプション | 各種定額サービス |

## カテゴリ一覧

**支出**: 食費 / 日用品 / 交通費 / 娯楽・趣味 / 通信費 / 光熱費 / 医療費 / 保険 / 住居費 / 教育費 / 被服費 / 美容・理容 / サブスクリプション / ネットショッピング / その他支出

**収入**: 給与 / 賞与 / 副収入 / 投資収益 / その他収入

## ファイル構成

```
05_家計簿/
├── main.py                  # メインスクリプト
├── email_fetcher.py         # Gmail IMAP取得
├── transaction_extractor.py # Claude APIで取引抽出
├── budget_generator.py      # Markdownレポート生成
├── requirements.txt         # 依存パッケージ
├── .env.example             # 設定テンプレート
└── output/                  # 生成されたレポート（自動作成）
```
