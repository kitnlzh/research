"""ベクトルDB（Chroma）と embedding の管理。

embedding の選択順（要件10〜12）:
    1. OPENAI_API_KEY があれば OpenAI embedding（第一候補）
    2. sentence-transformers が入っていればローカル embedding（fallback）
    3. どちらも無ければ、キー不要のハッシュベース簡易 embedding
       → APIキーが無くても「取り込み・ローカルDB保存」まで必ず動く

簡易 embedding は意味検索の精度は高くないが、パイプライン全体を
APIキー無しで動作確認できることを優先した割り切り実装。
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from .chunking import Chunk
from .config import Settings
from .utils import explain_import_error, get_logger

logger = get_logger(__name__)

_HASH_DIM = 256  # 簡易 embedding の次元


# --------------------------------------------------------------------------- #
# Embedding backends
# --------------------------------------------------------------------------- #
@dataclass
class Embedder:
    """テキスト列を埋め込みベクトル列に変換するバックエンド。"""

    name: str
    embed: callable  # (list[str]) -> list[list[float]]


def _tokenize(text: str) -> list[str]:
    """言語非依存の簡易トークナイズ。

    空白区切りの語（英数）に加え、文字バイグラムも生成する。
    日本語は空白が無いため、語分割だけでは検索が効かない。
    文字バイグラムを併用することで、日本語でも部分一致による
    類似度が出るようにする。
    """
    lowered = text.lower()
    tokens = [t for t in lowered.split() if t]
    # 空白・記号を除いた連続文字列から文字バイグラムを作る
    compact = "".join(ch for ch in lowered if not ch.isspace())
    bigrams = [compact[i : i + 2] for i in range(len(compact) - 1)]
    return tokens + bigrams


def _hash_embedding(texts: list[str], dim: int = _HASH_DIM) -> list[list[float]]:
    """キー不要の決定的 embedding。トークンを md5 でビン分割した TF ベクトル。

    語＋文字バイグラムを特徴量にするため、日本語文書でも検索が機能する。
    """
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        for tok in _tokenize(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % dim] += 1.0
        # L2 正規化（コサイン類似度を安定させる）
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def _openai_embedder(settings: Settings) -> Embedder:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.openai_embedding_model

    def embed(texts: list[str]) -> list[list[float]]:
        # OpenAI は一度に多数渡せるが、安全のため分割
        out: list[list[float]] = []
        batch = 64
        for i in range(0, len(texts), batch):
            resp = client.embeddings.create(model=model, input=texts[i : i + batch])
            out.extend(d.embedding for d in resp.data)
        return out

    return Embedder(name=f"openai:{model}", embed=embed)


def _sentence_transformers_embedder() -> Embedder:
    from sentence_transformers import SentenceTransformer

    # 日本語も扱える多言語モデル
    model_name = "paraphrase-multilingual-MiniLM-L12-v2"
    model = SentenceTransformer(model_name)

    def embed(texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]

    return Embedder(name=f"sbert:{model_name}", embed=embed)


def get_embedder(settings: Settings) -> Embedder:
    """利用可能な embedding バックエンドを選択して返す。"""
    if settings.has_openai:
        try:
            emb = _openai_embedder(settings)
            logger.info("Embedding: OpenAI を使用 (%s)", emb.name)
            return emb
        except ImportError:
            logger.warning(
                "openai 未導入のため OpenAI embedding を使えません。fallback します。"
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("OpenAI embedding 初期化失敗: %s。fallback します。", e)

    try:
        emb = _sentence_transformers_embedder()
        logger.info("Embedding: ローカル sentence-transformers を使用 (%s)", emb.name)
        return emb
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        logger.warning("sentence-transformers 初期化失敗: %s", e)

    logger.warning(
        "OpenAI/sentence-transformers いずれも使えないため、簡易ハッシュ embedding を使用します"
        "（意味検索の精度は限定的。動作確認用）。"
    )
    return Embedder(name="hash-fallback", embed=lambda ts: _hash_embedding(ts))


# --------------------------------------------------------------------------- #
# Chroma store
# --------------------------------------------------------------------------- #
class VectorStore:
    """Chroma の PersistentClient ラッパ。embedding は外部で計算して渡す。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            import chromadb
        except ImportError as e:
            raise ImportError(explain_import_error("chromadb")) from e

        self._client = chromadb.PersistentClient(path=settings.persist_dir)
        # 我々が embedding を計算するので embedding_function は使わない
        self._collection = self._client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = get_embedder(settings)

    @property
    def embedder_name(self) -> str:
        return self._embedder.name

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """チャンクを embedding して追加。冪等性のため決定的 ID を使う。"""
        if not chunks:
            return 0
        texts = [c.text for c in chunks]
        embeddings = self._embedder.embed(texts)

        ids, metadatas, docs = [], [], []
        for c, text in zip(chunks, texts):
            src = c.metadata.get("source", "unknown")
            page = c.metadata.get("page")
            chunk_no = c.metadata.get("chunk", 0)
            raw_id = f"{src}|p{page}|c{chunk_no}|{hashlib.md5(text.encode()).hexdigest()[:8]}"
            ids.append(raw_id)
            # Chroma は None メタ値を許さないので空文字に正規化
            metadatas.append(
                {
                    "source": str(src),
                    "page": "" if page is None else str(page),
                    "chunk": str(chunk_no),
                }
            )
            docs.append(text)

        # upsert で再取り込み時の重複を防ぐ
        self._collection.upsert(
            ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs
        )
        return len(ids)

    def count(self) -> int:
        return self._collection.count()

    def query(self, question: str, k: int = 6) -> list[dict]:
        """質問文を embedding して関連チャンクを返す。"""
        q_emb = self._embedder.embed([question])[0]
        res = self._collection.query(
            query_embeddings=[q_emb],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict] = []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            hits.append(
                {
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page", ""),
                    "chunk": meta.get("chunk", ""),
                    "distance": dist,
                }
            )
        return hits
