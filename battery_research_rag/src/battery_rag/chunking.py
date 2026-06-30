"""文書のチャンク分割。

日本語を含む文書を、文字数ベースでオーバーラップ付きに分割する。
段落（空行）境界をできるだけ尊重しつつ、長すぎる段落は文字数で割る。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .loaders import Document


@dataclass
class Chunk:
    """ベクトルDBに格納する最小単位。"""

    text: str
    metadata: dict = field(default_factory=dict)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """文字数ベースのスライディングウィンドウ分割。

    まず段落で区切り、各塊を chunk_size に収まるよう連結／分割する。
    """
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""

    def flush(b: str) -> None:
        if b.strip():
            chunks.append(b.strip())

    for para in paragraphs:
        if len(para) > chunk_size:
            # 長い段落はバッファを吐き出してから window 分割
            flush(buf)
            buf = ""
            start = 0
            step = max(1, chunk_size - overlap)
            while start < len(para):
                chunks.append(para[start : start + chunk_size])
                start += step
            continue
        if len(buf) + len(para) + 2 <= chunk_size:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            flush(buf)
            # オーバーラップ分を引き継ぐ
            tail = buf[-overlap:] if overlap and buf else ""
            buf = f"{tail}\n\n{para}".strip() if tail else para
    flush(buf)
    return chunks


def chunk_documents(
    documents: list[Document], chunk_size: int = 800, overlap: int = 150
) -> list[Chunk]:
    """Document リストを Chunk リストに変換する。

    各 Chunk のメタデータには source / page に加え、chunk 番号を付与する。
    """
    chunks: list[Chunk] = []
    for doc in documents:
        pieces = _split_text(doc.text, chunk_size, overlap)
        for j, piece in enumerate(pieces):
            meta = dict(doc.metadata)
            meta["chunk"] = j
            chunks.append(Chunk(text=piece, metadata=meta))
    return chunks
