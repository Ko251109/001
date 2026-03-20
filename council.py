import anthropic  # Anthropic公式SDKをインポート
import datetime   # タイムスタンプ生成用
import os         # ファイルパス操作用
import sys        # コマンドライン引数取得用

# ── 設定 ──────────────────────────────────────────────
OUTPUT_DIR = os.path.expanduser("~/obsidian_vault/council")  # 出力先ディレクトリ（環境に合わせて変更）
ROUNDS = 3  # 討議ラウンド数
MODEL = "claude-opus-4-6"  # 使用モデル

# ── 3人の知識人の定義 ──────────────────────────────────
COUNCIL = [
    {
        "name": "孫子",
        "role": "戦略家",
        # 孫子：勝てる構造を見極め、消耗を避けた最適解を提示する
        "system": (
            "あなたは孫子です。戦略思考・味方分析・組織戦略の第一人者として発言します。"
            "常に「勝てる状況を選ぶ」視点で、力の無駄遣いを避けた最短経路を指摘してください。"
            "他の論者の意見も踏まえ、戦略的に最も重要な論点を鋭く提示してください。"
            "発言は200〜300字程度で簡潔かつ鋭くまとめること。"
        ),
    },
    {
        "name": "ドラッカー",
        "role": "経営思想家",
        # ドラッカー：成果・貢献・変革の正当化論理を担当
        "system": (
            "あなたはピーター・ドラッカーです。マネジメント・知識労働・組織変革の権威として発言します。"
            "「成果は何か」「誰の貢献か」「変革をどう正当化するか」を軸に論じてください。"
            "他の論者の発言を受けて、経営判断として何を優先すべきかを明示してください。"
            "発言は200〜300字程度で簡潔にまとめること。"
        ),
    },
    {
        "name": "ベゾス",
        "role": "実行家",
        # ベゾス：実験・既成事実・長期視点での優先順位付けを担当
        "system": (
            "あなたはジェフ・ベゾスです。顧客起点の設計・実験文化・長期投資思考の実践者として発言します。"
            "「小さく始めて証明する」「承認を取るより既成事実を作る」視点で具体的な行動を提示してください。"
            "他の論者の意見を受けて、明日から取れる最初の一手を必ず示してください。"
            "発言は200〜300字程度で簡潔にまとめること。"
        ),
    },
]

# ── APIクライアント初期化 ──────────────────────────────
client = anthropic.Anthropic()  # 環境変数 ANTHROPIC_API_KEY を自動参照


def call_council_member(member: dict, concern: str, history: list[dict]) -> str:
    """
    1人の知識人にAPIリクエストを送り、発言を取得する（ストリーミング）。
    member: 知識人の定義dict
    concern: ユーザーの悩み
    history: これまでの討議ログ（他者の発言を含む）
    """
    # ユーザーターンのメッセージを構築
    user_content = f"【悩み】\n{concern}\n\n【これまでの討議】\n"
    if history:
        for entry in history:
            user_content += f"\n■ {entry['name']}（{entry['role']}）\n{entry['content']}\n"
    else:
        user_content += "（まだ発言なし。あなたが最初の発言者です）"

    user_content += f"\n\n上記を踏まえ、{member['name']}として発言してください。"

    # ストリーミングでAPIを呼び出す
    full_text = ""
    with client.messages.stream(
        model=MODEL,
        max_tokens=600,  # 1発言あたりの上限トークン
        thinking={"type": "adaptive"},  # 適応型思考（Opus 4.6推奨）
        system=member["system"],  # その知識人のペルソナ設定
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text

    return full_text


def synthesize_conclusion(concern: str, full_history: list[dict]) -> str:
    """
    3人の討議全体を受けて、最終合意・結論を生成する（ストリーミング）。
    """
    history_text = ""
    for entry in full_history:
        history_text += f"\n■ {entry['name']}（{entry['role']}）Round {entry['round']}\n{entry['content']}\n"

    prompt = (
        f"【悩み】\n{concern}\n\n"
        f"【討議ログ】\n{history_text}\n\n"
        "上記の討議を踏まえ、3人の合意として「結論」と「明日から取れる具体的な第一歩」をまとめてください。"
        "形式：\n## 合議結論\n（結論）\n\n## 推奨する第一歩\n（具体的アクション）"
    )

    full_text = ""
    with client.messages.stream(
        model=MODEL,
        max_tokens=800,
        thinking={"type": "adaptive"},
        system="あなたは孫子・ドラッカー・ベゾスの討議を記録する書記官です。3者の議論を客観的に統合し、実践的な結論を導いてください。",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text

    return full_text


def save_to_markdown(concern: str, full_history: list[dict], conclusion: str) -> str:
    """
    討議ログと結論をMarkdownファイルに保存する。
    戻り値：保存先ファイルパス
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)  # 出力ディレクトリが存在しない場合は作成

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # ファイル名用タイムスタンプ
    filepath = os.path.join(OUTPUT_DIR, f"{timestamp}_council.md")  # ファイルパスを組み立て

    lines = [
        f"# 合議ログ\n",
        f"**日時**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n",
        f"**悩み**: {concern}\n\n",
        "---\n\n",
        "## 討議ログ\n",
    ]

    current_round = 0
    for entry in full_history:
        if entry["round"] != current_round:  # ラウンドが変わったら見出しを挿入
            current_round = entry["round"]
            lines.append(f"\n### Round {current_round}\n")
        lines.append(f"\n#### {entry['name']}（{entry['role']}）\n{entry['content']}\n")

    lines.append("\n---\n\n")
    lines.append(conclusion)  # 最終結論を末尾に追記

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)  # ファイルに書き込む

    return filepath


def run_council(concern: str) -> None:
    """
    合議セッションのメインロジック。
    """
    print(f"\n合議開始\n悩み：{concern}\n{'─'*50}")

    full_history: list[dict] = []  # 全発言を時系列で蓄積

    # ── 討議ラウンドを実行 ──
    for round_num in range(1, ROUNDS + 1):
        print(f"\n【Round {round_num}】")
        round_history = [e for e in full_history]  # このラウンド開始時点の履歴を渡す

        for member in COUNCIL:
            print(f"  {member['name']} が発言中...", end="", flush=True)
            content = call_council_member(member, concern, round_history)  # 発言を取得
            entry = {
                "round": round_num,
                "name": member["name"],
                "role": member["role"],
                "content": content,
            }
            full_history.append(entry)   # 全履歴に追加
            round_history.append(entry)  # このラウンドの履歴にも追加（後続の同ラウンド発言者が参照）
            print(f" 完了")

    # ── 結論生成 ──
    print(f"\n{'─'*50}\n結論を生成中...")
    conclusion = synthesize_conclusion(concern, full_history)

    # ── Markdown保存 ──
    filepath = save_to_markdown(concern, full_history, conclusion)
    print(f"\n保存完了：{filepath}")

    # ── ターミナルにも結論を表示 ──
    print(f"\n{'═'*50}\n{conclusion}\n{'═'*50}\n")


# ── エントリーポイント ──────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        concern = " ".join(sys.argv[1:])  # CLIの引数から悩みを受け取る
    else:
        concern = input("悩みを入力してください：").strip()  # 引数なしの場合は対話入力

    if not concern:
        print("悩みが入力されていません。終了します。")
        sys.exit(1)

    run_council(concern)  # 合議セッションを開始
