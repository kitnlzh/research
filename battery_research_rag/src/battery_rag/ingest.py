"""文書取り込みCLI。

使い方:
    python -m battery_rag.ingest --data-dir data --persist-dir chroma_db
"""

from __future__ import annotations

import argparse
import sys

from .chunking import chunk_documents
from .config import load_settings
from .loaders import load_directory
from .utils import get_logger

logger = get_logger("battery_rag.ingest")


def run(data_dir: str, persist_dir: str) -> int:
    settings = load_settings()
    # CLI 引数で上書き
    settings = settings.__class__(
        **{**settings.__dict__, "data_dir": data_dir, "persist_dir": persist_dir}
    )

    logger.info("データディレクトリ: %s", settings.data_dir)
    logger.info("永続化ディレクトリ: %s", settings.persist_dir)

    documents = load_directory(settings.data_dir)
    if not documents:
        logger.warning("取り込む文書がありません。data/ にPDF/txt/md/csvを置いてください。")
        return 0

    chunks = chunk_documents(
        documents, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    logger.info("生成チャンク数: %d", len(chunks))

    # VectorStore は chromadb を要求するため、ここで遅延 import
    from .vector_store import VectorStore

    store = VectorStore(settings)
    logger.info("使用 embedding: %s", store.embedder_name)
    added = store.add_chunks(chunks)
    logger.info("ベクトルDBに登録: %d チャンク（総数 %d）", added, store.count())
    print(f"取り込み完了: {added} チャンクを {settings.persist_dir} に保存しました。")
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="data/ 配下の文書を取り込み、Chroma ローカルDBに保存する。"
    )
    parser.add_argument("--data-dir", default="data", help="入力ディレクトリ（既定: data）")
    parser.add_argument(
        "--persist-dir", default="chroma_db", help="ChromaDB 保存先（既定: chroma_db）"
    )
    args = parser.parse_args(argv)

    try:
        run(args.data_dir, args.persist_dir)
        return 0
    except ImportError as e:
        logger.error("必要なライブラリが不足しています: %s", e)
        return 2
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        logger.error("取り込み中にエラー: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
