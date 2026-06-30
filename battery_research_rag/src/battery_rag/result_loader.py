"""実験結果CSVの読み込み・整理CLI。

使い方:
    python -m battery_rag.result_loader --csv data/results/sample_results.csv

想定列（存在する列だけ使い、欠けても落ちない）:
    experiment_id, date, case, market_pattern, objective_value,
    spot_revenue, reserve_revenue, degradation_cost,
    avg_soc, min_soc, max_soc, total_charge, total_discharge, max_dod, comment
"""

from __future__ import annotations

import argparse
import sys

from .utils import explain_import_error, get_logger

logger = get_logger("battery_rag.result_loader")

# 列の分類
NUMERIC_COLS = [
    "objective_value",
    "spot_revenue",
    "reserve_revenue",
    "degradation_cost",
    "avg_soc",
    "min_soc",
    "max_soc",
    "total_charge",
    "total_discharge",
    "max_dod",
]
KEY_COLS = ["experiment_id", "date", "case", "market_pattern"]
EXPECTED_COLS = KEY_COLS + NUMERIC_COLS + ["comment"]


def load_results(csv_path: str):
    """CSV を DataFrame として読み込む。数値列は数値化する。"""
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(explain_import_error("pandas")) from e

    df = pd.read_csv(csv_path)
    # 数値列を数値化（変換できない値は NaN）
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def summarize(df) -> dict:
    """存在する列だけで要約統計を作る。"""
    present = [c for c in EXPECTED_COLS if c in df.columns]
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    extra = [c for c in df.columns if c not in EXPECTED_COLS]

    numeric_present = [c for c in NUMERIC_COLS if c in df.columns]
    stats = {}
    for col in numeric_present:
        series = df[col].dropna()
        if series.empty:
            continue
        stats[col] = {
            "count": int(series.count()),
            "mean": float(series.mean()),
            "min": float(series.min()),
            "max": float(series.max()),
        }

    cases = sorted(map(str, df["case"].dropna().unique())) if "case" in df.columns else []
    patterns = (
        sorted(map(str, df["market_pattern"].dropna().unique()))
        if "market_pattern" in df.columns
        else []
    )

    return {
        "n_rows": int(len(df)),
        "present_columns": present,
        "missing_columns": missing,
        "extra_columns": extra,
        "cases": cases,
        "market_patterns": patterns,
        "numeric_stats": stats,
    }


def print_summary(df, summary: dict) -> None:
    print("=== 実験結果サマリ ===")
    print(f"行数: {summary['n_rows']}")
    print(f"利用可能な想定列: {', '.join(summary['present_columns']) or '(なし)'}")
    if summary["missing_columns"]:
        print(f"欠けている想定列: {', '.join(summary['missing_columns'])}")
    if summary["extra_columns"]:
        print(f"想定外の追加列: {', '.join(summary['extra_columns'])}")
    if summary["cases"]:
        print(f"Case: {', '.join(summary['cases'])}")
    if summary["market_patterns"]:
        print(f"市場パターン: {', '.join(summary['market_patterns'])}")

    if summary["numeric_stats"]:
        print("\n--- 数値指標の統計 ---")
        print(f"{'指標':<20}{'件数':>6}{'平均':>16}{'最小':>16}{'最大':>16}")
        for col, s in summary["numeric_stats"].items():
            print(
                f"{col:<20}{s['count']:>6}{s['mean']:>16.4g}"
                f"{s['min']:>16.4g}{s['max']:>16.4g}"
            )
    else:
        print("\n数値指標の列が見つかりませんでした。")


def run(csv_path: str) -> dict:
    df = load_results(csv_path)
    summary = summarize(df)
    print_summary(df, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="実験結果CSVを読み込んで要約表示する。")
    parser.add_argument("--csv", required=True, help="実験結果CSVのパス")
    args = parser.parse_args(argv)

    try:
        run(args.csv)
        return 0
    except ImportError as e:
        logger.error("必要なライブラリが不足しています: %s", e)
        return 2
    except FileNotFoundError:
        logger.error("CSVが見つかりません: %s", args.csv)
        return 2
    except Exception as e:  # noqa: BLE001
        logger.error("CSV処理中にエラー: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
