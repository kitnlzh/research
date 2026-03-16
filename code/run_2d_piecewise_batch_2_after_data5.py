from __future__ import annotations

import itertools
import os
import shutil
from datetime import datetime
from pathlib import Path

import gurobipy as gp
import pandas as pd

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


def load_data5_inputs(
    data5_path: Path,
    spot_col: str,
    pri_col: str,
    sec_col: str,
) -> tuple[list[float], list[float], list[float]]:
    df = read_excel_with_fallback(data5_path, sheet_name=0)

    for c in (spot_col, pri_col, sec_col):
        if c not in df.columns:
            raise KeyError(f"Column '{c}' not found in {data5_path}")

    lambda_t = df[spot_col].tolist()[:48]
    r_b = df[pri_col].dropna().tolist()[:8]
    r2_b = df[sec_col].dropna().tolist()[:8]

    if len(lambda_t) != 48:
        raise ValueError(f"{spot_col} length must be 48, got {len(lambda_t)}")
    if len(r_b) != 8:
        raise ValueError(f"{pri_col} length must be 8, got {len(r_b)}")
    if len(r2_b) != 8:
        raise ValueError(f"{sec_col} length must be 8, got {len(r2_b)}")

    vals = lambda_t + r_b + r2_b
    if any(pd.isna(v) for v in vals):
        raise ValueError(f"Data5 contains NaN in {spot_col}/{pri_col}/{sec_col} required range")

    return [float(v) for v in lambda_t], [float(v) for v in r_b], [float(v) for v in r2_b]


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


def zero_like(mat):
    return [[0.0 for _ in row] for row in mat]


def main() -> None:
    data5_path_env = os.getenv("DATA5_PATH")
    cycle_path_env = os.getenv("CYCLE_PATH")

    data5_path = Path(data5_path_env) if data5_path_env else find_file_under_onedrive("Data5.xlsx")
    cycle_path = Path(cycle_path_env) if cycle_path_env else find_file_under_onedrive("0704サイクル劣化.xlsx")

    if data5_path is None:
        raise FileNotFoundError("Data5.xlsx not found under OneDrive")
    if cycle_path is None:
        raise FileNotFoundError("0704サイクル劣化.xlsx not found under OneDrive")
    if not data5_path.exists():
        raise FileNotFoundError(f"DATA5_PATH not found: {data5_path}")
    if not cycle_path.exists():
        raise FileNotFoundError(f"CYCLE_PATH not found: {cycle_path}")

    run_root = make_run_dir(prefix="2d_piecewise_batch_2_data5_after")
    print(f"[INFO] run_root = {run_root}")
    print(f"[INFO] data5_path = {data5_path}")
    print(f"[INFO] cycle_path = {cycle_path}")

    s_mat, t_mat, s10_mat, t10_mat = load_cycle_tables(cycle_path)

    no_deg = os.getenv("NO_DEGRADATION", "0").strip().lower() in ("1", "true", "yes", "on")
    if no_deg:
        s_mat = zero_like(s_mat)
        t_mat = zero_like(t_mat)
        s10_mat = zero_like(s10_mat)
        t10_mat = zero_like(t10_mat)
        print("[INFO] NO_DEGRADATION=1 -> S/T/S10/T10 are replaced with zero matrices")
    profiles = [
        ("spot5", "pri5", "sec5", "s5p5c5"),
        ("spot6", "pri6", "sec6", "s6p6c6"),
    ]

    cases = build_cases()

    max_cases_env = os.getenv("MAX_CASES")
    if max_cases_env:
        n_case = int(max_cases_env)
        cases = cases[:n_case]
        print(f"[INFO] MAX_CASES={n_case} -> using first {len(cases)} cases")

    results: list[dict] = []

    for spot_col, pri_col, sec_col, ptag in profiles:
        lambda_t, r_b, r2_b = load_data5_inputs(
            data5_path=data5_path,
            spot_col=spot_col,
            pri_col=pri_col,
            sec_col=sec_col,
        )

        profile_name = f"Data5_{spot_col}_{pri_col}_{sec_col}"
        profile_dir = run_root / profile_name
        profile_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] profile={profile_name}, cases={len(cases)}")

        for idx, (fix_k0, fix_k1, fix_k2) in enumerate(cases, start=1):
            label = f"k0{tag(fix_k0)}k1{tag(fix_k1)}k2{tag(fix_k2)}"
            case_id = f"c{idx:02d}"
            case_dir = profile_dir / f"{case_id}_{label}"
            case_dir.mkdir(parents=True, exist_ok=True)

            print(f"[INFO] solving {profile_name} {case_id} {label}")

            res = core.solve_one_case(
                run_dir=case_dir,
                lambda_t=lambda_t,
                R_b=r_b,
                R2_b=r2_b,
                S_mat=s_mat,
                T_mat=t_mat,
                S10_mat=s10_mat,
                T10_mat=t10_mat,
                fix_k0=fix_k0,
                fix_k1=fix_k1,
                fix_k2=fix_k2,
            )

            sheet_name = f"{ptag}_{case_id}"[:31]
            res.update(
                {
                    "profile": profile_name,
                    "spot_col": spot_col,
                    "pri_col": pri_col,
                    "sec_col": sec_col,
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
