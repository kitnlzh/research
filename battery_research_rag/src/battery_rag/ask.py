"""質問応答CLI。

使い方:
    python -m battery_rag.ask "2次元劣化モデルを入れる意味を説明して" --k 6

OPENAI_API_KEY がある場合は検索した根拠をLLMに渡して日本語回答を生成する。
無い場合は、検索でヒットした根拠チャンク（ファイル名・ページ・チャンク）を表示する
（要件10: キーが無くても取り込み・検索・DB保存までは動く）。
"""

from __future__ import annotations

import argparse
import sys

from .config import load_settings, read_prompt
from .utils import get_logger

logger = get_logger("battery_rag.ask")

DEFAULT_SYSTEM_PROMPT = (
    "あなたは定置用蓄電池運用，電力市場，数理最適化，劣化コスト分析に詳しい研究支援AIです。\n"
    "回答では，スポット市場，一次調整力市場，二次調整力市場，SOC，DoD，劣化コスト，MILP，"
    "ピースワイズ線形近似の観点を必要に応じて使ってください。\n"
    "根拠資料にないことは断定しないでください。\n"
    "不確かな場合は「資料からは判断できない」と述べてください。\n"
    "出力は日本語で行ってください。\n"
    "研究発表や論文に使えるように，単なる感想ではなく，観測事実，解釈，限界，"
    "追加実験案に分けて述べてください。"
)


def _format_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        page = f" p.{h['page']}" if h.get("page") else ""
        blocks.append(f"[根拠{i}] {h['source']}{page} (chunk {h['chunk']})\n{h['text']}")
    return "\n\n".join(blocks)


def _print_sources(hits: list[dict]) -> None:
    print("\n--- 根拠（出典）---")
    for i, h in enumerate(hits, 1):
        page = f" p.{h['page']}" if h.get("page") else ""
        dist = h.get("distance")
        dist_s = f"  距離={dist:.4f}" if isinstance(dist, (int, float)) else ""
        print(f"[{i}] {h['source']}{page}  chunk {h['chunk']}{dist_s}")


def _generate_answer(question: str, hits: list[dict], settings) -> str | None:
    """OpenAI で回答生成。キーや openai が無ければ None。"""
    if not settings.has_openai:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai 未導入のため回答生成をスキップします。")
        return None

    system_prompt = read_prompt("system_prompt.txt", DEFAULT_SYSTEM_PROMPT)
    context = _format_context(hits)
    user_prompt = (
        f"以下の根拠資料のみを使って質問に答えてください。\n\n"
        f"=== 根拠資料 ===\n{context}\n\n"
        f"=== 質問 ===\n{question}\n\n"
        f"回答の最後に、使用した根拠番号（[根拠1] など）を明記してください。"
    )
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        logger.error("LLM 回答生成に失敗: %s", e)
        return None


def run(question: str, k: int, persist_dir: str | None = None) -> int:
    settings = load_settings()
    if persist_dir:
        settings = settings.__class__(**{**settings.__dict__, "persist_dir": persist_dir})

    from .vector_store import VectorStore

    store = VectorStore(settings)
    if store.count() == 0:
        print(
            "ベクトルDBが空です。先に取り込みを実行してください:\n"
            "  python -m battery_rag.ingest --data-dir data --persist-dir "
            f"{settings.persist_dir}"
        )
        return 0

    hits = store.query(question, k=k)
    if not hits:
        print("関連する根拠が見つかりませんでした。")
        return 0

    print(f"質問: {question}\n")
    answer = _generate_answer(question, hits, settings)
    if answer:
        print("=== 回答 ===")
        print(answer)
    else:
        print(
            "（OpenAI APIキーが未設定、または openai 未導入のため、回答生成は行いません。"
            "検索した根拠チャンクを表示します。.env に OPENAI_API_KEY を設定すると"
            "日本語回答を生成します。）"
        )
        for i, h in enumerate(hits, 1):
            page = f" p.{h['page']}" if h.get("page") else ""
            print(f"\n[根拠{i}] {h['source']}{page} (chunk {h['chunk']})")
            print(h["text"][:600])

    _print_sources(hits)
    return len(hits)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG でコレクションに質問する。")
    parser.add_argument("question", help="質問文（日本語可）")
    parser.add_argument("--k", type=int, default=6, help="検索する根拠数（既定: 6）")
    parser.add_argument("--persist-dir", default=None, help="ChromaDB の場所（既定: .env / chroma_db）")
    args = parser.parse_args(argv)

    try:
        run(args.question, args.k, args.persist_dir)
        return 0
    except ImportError as e:
        logger.error("必要なライブラリが不足しています: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        logger.error("質問処理中にエラー: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
