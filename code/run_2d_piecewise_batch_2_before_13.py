from __future__ import annotations

import itertools
import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import gurobipy as gp

import run_2d_piecewise_batch as core


CODE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CODE_DIR.parent
RESULT_DIR = PROJECT_DIR / "result"

_orig_build_gurobi_env = core.build_gurobi_env


def _load_wls_from_registry() -> None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            for k in ("GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID"):
                if os.getenv(k):
                    continue
                try:
                    v, _ = winreg.QueryValueEx(key, k)
                except OSError:
                    continue
                if v:
                    os.environ[k] = str(v)
    except Exception:
        # Keep silent and fallback to local license if registry access fails.
        pass


def build_gurobi_env_auto() -> gp.Env:
    # Prefer existing WLS settings when present; otherwise fallback to local license.
    if not (os.getenv("GRB_WLSACCESSID") and os.getenv("GRB_WLSSECRET") and os.getenv("GRB_LICENSEID")):
        _load_wls_from_registry()

    if os.getenv("GRB_WLSACCESSID") and os.getenv("GRB_WLSSECRET") and os.getenv("GRB_LICENSEID"):
        return _orig_build_gurobi_env()
    return gp.Env()


core.build_gurobi_env = build_gurobi_env_auto


def find_file_under_onedrive(filename: str) -> Path | None:
    start = Path.home() / "OneDrive"
    if not start.exists():
        start = Path(r"C:/Users/kit02/OneDrive")
    if not start.exists():
        return None

    for p in start.rglob(filename):
        if p.is_file():
            return p
    return None


def make_run_dir(prefix: str = "run") -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = RESULT_DIR / f"{prefix}_{ts}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_excel_with_fallback(path: Path, **kwargs) -> pd.DataFrame:
    try:
        return pd.read_excel(path, **kwargs)
    except PermissionError:
        tmp = CODE_DIR / f"_tmp_{path.stem}_{os.getpid()}{path.suffix}"
        shutil.copy2(path, tmp)
        return pd.read_excel(tmp, **kwargs)


def load_market_inputs(price_path: Path) -> pd.DataFrame:
    spot_df = read_excel_with_fallback(price_path, sheet_name="spot_48_wide")
    pri_df = read_excel_with_fallback(price_path, sheet_name="primary_1-0_8_wide")
    sec_df = read_excel_with_fallback(price_path, sheet_name="secondary_2-1_8_wide")

    merged = spot_df.merge(pri_df, on="date", how="left")
    merged = merged.merge(sec_df, on="date", how="left", suffixes=("_pri1_0", "_sec2_1"))
    merged["date"] = pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")

    required = [f"raw_t{i}" for i in range(1, 49)]
    required += [f"b{i:02d}_pri1_0" for i in range(1, 9)]
    required += [f"b{i:02d}_sec2_1" for i in range(1, 9)]

    missing_cols = [c for c in required if c not in merged.columns]
    if missing_cols:
        raise KeyError(f"Missing columns in {price_path}: {missing_cols}")

    return merged


def load_cycle_tables(cycle_path: Path):
    df_s = read_excel_with_fallback(cycle_path, sheet_name="s", header=None, usecols=range(4), nrows=4)
    df_t = read_excel_with_fallback(cycle_path, sheet_name="t", header=None, usecols=range(4), nrows=4)
    df_s10 = read_excel_with_fallback(cycle_path, sheet_name="s10", header=None, usecols=range(10), nrows=10)
    df_t10 = read_excel_with_fallback(cycle_path, sheet_name="t10", header=None, usecols=range(10), nrows=10)

    return (
        df_s.values.tolist(),
        df_t.values.tolist(),
        df_s10.values.tolist(),
        df_t10.values.tolist(),
    )


def build_cases() -> list[tuple[bool, bool, bool]]:
    cases: list[tuple[bool, bool, bool]] = []
    for fix_k0, fix_k1, fix_k2 in itertools.product([False, True], repeat=3):
        if fix_k0 and fix_k1 and fix_k2:
            continue
        cases.append((fix_k0, fix_k1, fix_k2))
    return cases


def tag(fix: bool) -> str:
    return "Z" if fix else "F"


def main() -> None:
    price_path = find_file_under_onedrive("selected_dates_price_trends_spot_1-0_2-1.xlsx")
    cycle_path = find_file_under_onedrive("0704サイクル劣化_before_piecewise.xlsx")

    if price_path is None:
        raise FileNotFoundError("selected_dates_price_trends_spot_1-0_2-1.xlsx not found under OneDrive")
    if cycle_path is None:
        raise FileNotFoundError("0704サイクル劣化_before_piecewise.xlsx not found under OneDrive")

    run_root = make_run_dir(prefix="2d_piecewise_batch_2_before")
    print(f"[INFO] run_root = {run_root}")
    print(f"[INFO] price_path = {price_path}")
    print(f"[INFO] cycle_path = {cycle_path}")

    market_df = load_market_inputs(price_path)

    max_dates_env = os.getenv("MAX_DATES")
    if max_dates_env:
        n = int(max_dates_env)
        market_df = market_df.head(n)
        print(f"[INFO] MAX_DATES={n} -> using first {len(market_df)} dates")

    S_mat, T_mat, S10_mat, T10_mat = load_cycle_tables(cycle_path)
    cases = build_cases()

    results: list[dict] = []

    for _, row in market_df.iterrows():
        date_str = str(row["date"])
        date_key = date_str.replace("-", "")
        date_dir = run_root / f"d{date_key}"
        date_dir.mkdir(parents=True, exist_ok=True)

        lambda_t = [float(row[f"raw_t{i}"]) for i in range(1, 49)]
        R_b = [float(row[f"b{i:02d}_pri1_0"]) for i in range(1, 9)]
        R2_b = [float(row[f"b{i:02d}_sec2_1"]) for i in range(1, 9)]

        vals = lambda_t + R_b + R2_b
        if any(pd.isna(v) for v in vals):
            print(f"[WARN] skip {date_str}: contains NaN")
            continue

        print(f"[INFO] solving date={date_str}, cases={len(cases)}")

        for idx, (fix_k0, fix_k1, fix_k2) in enumerate(cases, start=1):
            label = f"k0{tag(fix_k0)}k1{tag(fix_k1)}k2{tag(fix_k2)}"
            case_id = f"c{idx:02d}"
            case_dir = date_dir / f"{case_id}_{label}"
            case_dir.mkdir(parents=True, exist_ok=True)

            res = core.solve_one_case(
                run_dir=case_dir,
                lambda_t=lambda_t,
                R_b=R_b,
                R2_b=R2_b,
                S_mat=S_mat,
                T_mat=T_mat,
                S10_mat=S10_mat,
                T10_mat=T10_mat,
                fix_k0=fix_k0,
                fix_k1=fix_k1,
                fix_k2=fix_k2,
            )

            sheet_name = f"d{date_key}_{case_id}"[:31]
            res.update(
                {
                    "date": date_str,
                    "case_id": case_id,
                    "label": label,
                    "fix_k0": fix_k0,
                    "fix_k1": fix_k1,
                    "fix_k2": fix_k2,
                    "case_dir": str(case_dir),
                    "sheet": sheet_name,
                }
            )
            results.append(res)

    xlsx_path = run_root / "batch_results.xlsx"

    summary_rows = []
    for r in results:
        row = {k: v for k, v in r.items() if k not in ("k_df", "soc_df", "p_df", "delta_df")}
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)

        for r in results:
            sheet = str(r.get("sheet", "case"))[:31]

            k_df = r.get("k_df")
            if isinstance(k_df, pd.DataFrame):
                k_df.to_excel(writer, sheet_name=sheet, index=False, startrow=0)
                next_row = len(k_df) + 2
            else:
                next_row = 0

            soc_df = r.get("soc_df")
            if isinstance(soc_df, pd.DataFrame):
                soc_df.to_excel(writer, sheet_name=sheet, index=False, startrow=next_row)
                next_row = next_row + len(soc_df) + 2

            p_df = r.get("p_df")
            if isinstance(p_df, pd.DataFrame):
                p_df.to_excel(writer, sheet_name=sheet, index=False, startrow=next_row)
                next_row = next_row + len(p_df) + 2

            delta_df = r.get("delta_df")
            if isinstance(delta_df, pd.DataFrame):
                delta_df.to_excel(writer, sheet_name=sheet, index=False, startrow=next_row)

    print(f"[SAVE] {xlsx_path}")


if __name__ == "__main__":
    main()

