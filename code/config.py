# config.py
from pathlib import Path
from datetime import datetime

# 固定ルート（ユーザー指定）
CODE_DIR   = Path(r"C:\Users\kit02\OneDrive\研究\code")
EXCEL_DIR  = Path(r"C:\Users\kit02\OneDrive\研究\エクセル")
RESULT_DIR = Path(r"C:\Users\kit02\OneDrive\研究\result")

def ensure_dirs() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

def make_run_dir(prefix: str = "run") -> Path:
    """
    result配下に実行フォルダを作成して返す（衝突しにくいタイムスタンプ付き）
    """
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = RESULT_DIR / f"{prefix}_{ts}"
    d.mkdir(parents=True, exist_ok=True)
    return d
