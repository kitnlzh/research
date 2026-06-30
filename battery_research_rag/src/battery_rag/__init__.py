"""battery_rag: 定置用蓄電池の複数市場参加研究を支援する最小RAG実装。

サブモジュール:
    config          設定（.env 読み込み）
    loaders         PDF / txt / md / csv の読み込み
    chunking        文書のチャンク分割
    vector_store    Chroma ローカルベクトルDB と embedding
    ingest          文書取り込みCLI
    ask             質問応答CLI
    result_loader   実験結果CSVの整理CLI
    result_analyzer 実験結果の考察生成CLI
    utils           共通ユーティリティ
"""

__version__ = "0.1.0"
