"""実験結果の考察生成CLI。

使い方:
    python -m battery_rag.result_analyzer --csv data/results/sample_results.csv

OPENAI_API_KEY があれば、整理した数値サマリを analysis_prompt に基づき LLM に渡し、
研究発表・論文向けの考察を9項目構成で生成する。
キーが無い場合は、数値から機械的に作る「考察ドラフト（テンプレ）」を出力する
（要件10: APIキーが無くても落ちない）。

出力9項目:
    1. 実験条件の要約
    2. 数値結果の要約
    3. Case間の違い
    4. SOC運用の特徴
    5. 劣化コストの影響
    6. 市場運用上の解釈
    7. 研究上の主張候補
    8. 追加実験案
    9. 論文・発表に使える文章案
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_settings, read_prompt
from .result_loader import load_results, summarize
from .utils import get_logger

logger = get_logger("battery_rag.result_analyzer")

DEFAULT_ANALYSIS_PROMPT = (
    "あなたは定置用蓄電池の複数市場参加最適化に詳しい研究支援AIです。\n"
    "与えられた実験結果サマリ（JSON）をもとに、研究発表・論文に使える考察を作成してください。\n"
    "感想ではなく、観測事実・解釈・限界・追加実験案を分けて述べてください。\n"
    "数値に無い内容を断定せず、不確かなら「資料からは判断できない」と書いてください。\n"
    "必ず次の9見出しで日本語出力してください:\n"
    "1. 実験条件の要約\n2. 数値結果の要約\n3. Case間の違い\n4. SOC運用の特徴\n"
    "5. 劣化コストの影響\n6. 市場運用上の解釈\n7. 研究上の主張候補\n"
    "8. 追加実験案\n9. 論文・発表に使える文章案"
)

SECTIONS = [
    "1. 実験条件の要約",
    "2. 数値結果の要約",
    "3. Case間の違い",
    "4. SOC運用の特徴",
    "5. 劣化コストの影響",
    "6. 市場運用上の解釈",
    "7. 研究上の主張候補",
    "8. 追加実験案",
    "9. 論文・発表に使える文章案",
]


def _fmt(v) -> str:
    try:
        return f"{float(v):.4g}"
    except (TypeError, ValueError):
        return str(v)


def _case_comparison(df) -> list[str]:
    """Case 列があれば、case ごとに主要指標の平均を出す。"""
    lines: list[str] = []
    if "case" not in df.columns:
        return ["case 列が無いため Case 間比較はできません。"]
    metrics = [
        m
        for m in ["objective_value", "spot_revenue", "reserve_revenue", "degradation_cost", "avg_soc", "max_dod"]
        if m in df.columns
    ]
    if not metrics:
        return ["比較可能な数値指標が無いため Case 間比較はできません。"]
    grouped = df.groupby("case")[metrics].mean(numeric_only=True)
    for case, row in grouped.iterrows():
        parts = "; ".join(f"{m}={_fmt(row[m])}" for m in metrics)
        lines.append(f"- Case {case}: {parts}")
    return lines


def build_template_analysis(df, summary: dict) -> str:
    """LLM 無しでも出せる、数値ベースの考察ドラフト。"""
    stats = summary["numeric_stats"]
    out: list[str] = []

    out.append(SECTIONS[0])
    out.append(
        f"  実験 {summary['n_rows']} 件。"
        f"Case: {', '.join(summary['cases']) or '不明'}。"
        f"市場パターン: {', '.join(summary['market_patterns']) or '不明'}。"
    )

    out.append(SECTIONS[1])
    if stats:
        for col, s in stats.items():
            out.append(
                f"  {col}: 平均 {_fmt(s['mean'])}, 範囲 {_fmt(s['min'])}〜{_fmt(s['max'])} (n={s['count']})"
            )
    else:
        out.append("  数値指標が見つかりませんでした。")

    out.append(SECTIONS[2])
    out.extend("  " + line for line in _case_comparison(df))

    out.append(SECTIONS[3])
    soc_bits = []
    for c in ("avg_soc", "min_soc", "max_soc", "max_dod"):
        if c in stats:
            soc_bits.append(f"{c} 平均 {_fmt(stats[c]['mean'])}")
    out.append("  " + ("; ".join(soc_bits) if soc_bits else "SOC/DoD 指標が無く、運用特徴は判断できない。"))

    out.append(SECTIONS[4])
    if "degradation_cost" in stats:
        d = stats["degradation_cost"]
        rev = []
        if "spot_revenue" in stats:
            rev.append(("spot_revenue", stats["spot_revenue"]["mean"]))
        if "reserve_revenue" in stats:
            rev.append(("reserve_revenue", stats["reserve_revenue"]["mean"]))
        rev_sum = sum(v for _, v in rev) if rev else None
        ratio = (
            f"（収益合計平均 {_fmt(rev_sum)} に対し劣化コスト平均 {_fmt(d['mean'])}）"
            if rev_sum
            else ""
        )
        out.append(f"  劣化コスト 平均 {_fmt(d['mean'])}{ratio}。劣化を考慮した運用の妥当性検討が必要。")
    else:
        out.append("  degradation_cost 列が無く、劣化コストの影響は判断できない。")

    out.append(SECTIONS[5])
    out.append(
        "  スポット市場と調整力市場の同時参加では、収益最大化とSOC維持・劣化抑制が"
        "トレードオフになり得る。数値からは断定できない点は追加検証が必要。"
    )

    out.append(SECTIONS[6])
    out.append(
        "  （主張候補・要検証）2次元ピースワイズ劣化モデルの導入が目的関数値・劣化コストに"
        "与える影響を、Case 間比較から定量化できる可能性がある。"
    )

    out.append(SECTIONS[7])
    out.append("  - 市場パターン別の感度分析（一次/二次調整力の配分比を変える）")
    out.append("  - 劣化モデル次数（1次元 vs 2次元）の比較実験")
    out.append("  - SOC 上下限・初期SOC を変えた運用ロバスト性の確認")

    out.append(SECTIONS[8])
    out.append(
        "  本結果は、定置用蓄電池の複数市場同時参加において〔指標X〕が〔条件Y〕で改善した"
        "ことを示す。ただしサンプル数・前提条件に限界があり、一般化には追加実験を要する。"
    )

    out.append("\n（注）これは OpenAI APIキー未設定時のテンプレート考察です。"
               "OPENAI_API_KEY を設定すると、より具体的な考察を生成します。")
    return "\n".join(out)


def generate_llm_analysis(summary: dict, settings) -> str | None:
    if not settings.has_openai:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai 未導入のためテンプレート考察に切り替えます。")
        return None

    prompt = read_prompt("analysis_prompt.txt", DEFAULT_ANALYSIS_PROMPT)
    user = (
        "次の実験結果サマリ(JSON)を考察してください。\n\n"
        f"{json.dumps(summary, ensure_ascii=False, indent=2)}"
    )
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        logger.error("LLM 考察生成に失敗: %s。テンプレートに切り替えます。", e)
        return None


def run(csv_path: str) -> int:
    settings = load_settings()
    df = load_results(csv_path)
    summary = summarize(df)

    print(f"=== 実験結果の考察: {csv_path} ===\n")
    analysis = generate_llm_analysis(summary, settings)
    if analysis:
        print(analysis)
    else:
        print(build_template_analysis(df, summary))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="実験結果CSVから考察を生成する。")
    parser.add_argument("--csv", required=True, help="実験結果CSVのパス")
    args = parser.parse_args(argv)

    try:
        return run(args.csv)
    except ImportError as e:
        logger.error("必要なライブラリが不足しています: %s", e)
        return 2
    except FileNotFoundError:
        logger.error("CSVが見つかりません: %s", args.csv)
        return 2
    except Exception as e:  # noqa: BLE001
        logger.error("考察生成中にエラー: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
