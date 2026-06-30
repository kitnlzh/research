"""文書ローダ：PDF / txt / md / csv を読み込み、(text, metadata) の単位に変換する。

返す単位を「ドキュメント断片(Document)」と呼ぶ。チャンク分割は chunking.py が担当。
ここでは「ファイル単位」または「PDFはページ単位」でテキストを取り出す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .utils import explain_import_error, get_logger

logger = get_logger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".csv"}


@dataclass
class Document:
    """読み込んだ生テキストとメタデータ。"""

    text: str
    metadata: dict = field(default_factory=dict)


def _load_text_file(path: Path) -> list[Document]:
    """txt / md をUTF-8（失敗時はcp932）で読む。"""
    for enc in ("utf-8", "cp932", "utf-16"):
        try:
            text = path.read_text(encoding=enc)
            return [Document(text=text, metadata={"source": path.name, "page": None})]
        except UnicodeDecodeError:
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("テキスト読み込み失敗 %s: %s", path.name, e)
            return []
    logger.warning("文字コード判定に失敗しました: %s", path.name)
    return []


def _load_csv_file(path: Path) -> list[Document]:
    """csv を pandas で読み、行をテキスト化する。RAG検索の素材にする。

    実験結果CSVそのものの構造化処理は result_loader.py が担当するが、
    ここでは「検索可能なテキスト」として全体を取り込む。
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(explain_import_error("pandas")) from e

    try:
        df = pd.read_csv(path)
    except Exception as e:  # noqa: BLE001
        logger.warning("CSV読み込み失敗 %s: %s", path.name, e)
        return []

    lines = [f"CSVファイル: {path.name}", f"列: {', '.join(map(str, df.columns))}"]
    for i, row in df.iterrows():
        cells = "; ".join(f"{c}={row[c]}" for c in df.columns)
        lines.append(f"行{i}: {cells}")
    text = "\n".join(lines)
    return [Document(text=text, metadata={"source": path.name, "page": None})]


def _load_pdf_file(path: Path) -> list[Document]:
    """PDF をページ単位で読む。pypdf を第一候補、PyMuPDF(fitz) を次点。"""
    # pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        docs: list[Document] = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as e:  # noqa: BLE001
                logger.warning("%s ページ%d 抽出失敗: %s", path.name, i + 1, e)
                text = ""
            if text.strip():
                docs.append(
                    Document(text=text, metadata={"source": path.name, "page": i + 1})
                )
        if docs:
            return docs
        logger.warning("%s からテキストを抽出できませんでした（画像PDFの可能性）", path.name)
        return docs
    except ImportError:
        pass  # PyMuPDF を試す

    try:
        import fitz  # PyMuPDF

        docs = []
        with fitz.open(str(path)) as pdf:
            for i, page in enumerate(pdf):
                text = page.get_text() or ""
                if text.strip():
                    docs.append(
                        Document(
                            text=text, metadata={"source": path.name, "page": i + 1}
                        )
                    )
        return docs
    except ImportError as e:
        raise ImportError(explain_import_error("pypdf", "pypdf  # または PyMuPDF")) from e
    except Exception as e:  # noqa: BLE001
        logger.warning("PDF読み込み失敗 %s: %s", path.name, e)
        return []


def load_file(path: Path) -> list[Document]:
    """1ファイルを拡張子に応じて読み込む。"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf_file(path)
    if suffix in (".txt", ".md"):
        return _load_text_file(path)
    if suffix == ".csv":
        return _load_csv_file(path)
    logger.info("未対応の拡張子をスキップ: %s", path.name)
    return []


def load_directory(data_dir: str | Path) -> list[Document]:
    """data_dir 配下を再帰的に走査し、対応形式をすべて読み込む。"""
    base = Path(data_dir)
    if not base.exists():
        raise FileNotFoundError(f"データディレクトリが存在しません: {base}")

    docs: list[Document] = []
    files = sorted(p for p in base.rglob("*") if p.is_file())
    targets = [p for p in files if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not targets:
        logger.warning("対応ファイルが見つかりませんでした: %s", base)
    for path in targets:
        logger.info("読み込み: %s", path.relative_to(base))
        try:
            docs.extend(load_file(path))
        except ImportError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("読み込みスキップ %s: %s", path.name, e)
    logger.info("読み込んだ生ドキュメント数: %d", len(docs))
    return docs
