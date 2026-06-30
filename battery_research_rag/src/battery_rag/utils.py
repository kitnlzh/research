"""共通ユーティリティ（ロギング、簡易例外整形など）。"""

from __future__ import annotations

import logging
import sys


def get_logger(name: str = "battery_rag") -> logging.Logger:
    """色なし・シンプルなロガーを返す。多重ハンドラ登録を防ぐ。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def explain_import_error(package: str, pip_name: str | None = None) -> str:
    """依存ライブラリ未導入時に何を入れればよいか伝えるメッセージ。"""
    pip_name = pip_name or package
    return (
        f"'{package}' が見つかりません。次でインストールしてください: "
        f"pip install {pip_name}  "
        f"（または requirements.txt を pip install -r でまとめて導入）"
    )


def short(text: str, n: int = 300) -> str:
    """長い文字列をログ表示用に短縮する。"""
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"
