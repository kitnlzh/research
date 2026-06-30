"""設定値の一元管理。

すべて .env または環境変数から読み込む。APIキーはコードに直書きしない。
.env が無い／python-dotenv が未導入でも、環境変数だけで動作する。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# .env を読み込む（python-dotenv が無くても落ちない）
try:  # pragma: no cover - 環境依存
    from dotenv import load_dotenv

    # battery_research_rag/.env を優先的に探す
    _here = Path(__file__).resolve()
    _project_root = _here.parents[2]  # src/battery_rag/ -> src -> battery_research_rag
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
    else:
        load_dotenv()  # カレント等の .env を探す
except Exception:  # noqa: BLE001 - dotenv 未導入や読み込み失敗でも続行
    pass


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


@dataclass(frozen=True)
class Settings:
    """実行時設定。環境変数から構築する。"""

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # --- パス ---
    data_dir: str = "data"
    persist_dir: str = "chroma_db"
    collection_name: str = "battery_research"

    # --- チャンク分割 ---
    chunk_size: int = 800          # 文字数
    chunk_overlap: int = 150       # 文字数

    # --- 検索 ---
    top_k: int = 6

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    """環境変数から Settings を構築する。"""
    return Settings(
        openai_api_key=_get("OPENAI_API_KEY"),
        openai_embedding_model=_get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_chat_model=_get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        data_dir=_get("RAG_DATA_DIR", "data"),
        persist_dir=_get("RAG_PERSIST_DIR", "chroma_db"),
        collection_name=_get("RAG_COLLECTION", "battery_research"),
        chunk_size=int(_get("RAG_CHUNK_SIZE", "800") or "800"),
        chunk_overlap=int(_get("RAG_CHUNK_OVERLAP", "150") or "150"),
        top_k=int(_get("RAG_TOP_K", "6") or "6"),
    )


# プロンプトファイルの場所
def prompts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"


def read_prompt(filename: str, fallback: str = "") -> str:
    """prompts/ 配下のテキストを読む。無ければ fallback。"""
    path = prompts_dir() / filename
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return fallback
