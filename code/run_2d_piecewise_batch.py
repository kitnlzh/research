
# -*- coding: utf-8 -*-
"""
VSCode / ローカル実行用（パス固定・出力保存対応版）

入力Excel：
  C:\\Users\\kit02\\OneDrive\\研究\\エクセル

出力：
  C:\\Users\\kit02\\OneDrive\\研究\\result\\<run_YYYYmmdd_HHMMSS>\\
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
import itertools

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import gurobipy as gp
from gurobipy import Model, GRB


# =========================
# パス設定（ユーザー指定）
# =========================
CODE_DIR = Path(r"C:\Users\kit02\OneDrive\研究\code")
EXCEL_DIR = Path(r"C:\Users\kit02\OneDrive\研究\エクセル")
RESULT_DIR = Path(r"C:\Users\kit02\OneDrive\研究\result")


def make_run_dir(prefix: str = "run") -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = RESULT_DIR / f"{prefix}_{ts}"
    d.mkdir(parents=True, exist_ok=True)
    return d


# =========================
# Gurobi WLS設定
# =========================
def build_gurobi_env() -> gp.Env:
    """
    Gurobi WLSを環境変数から読み込んで初期化する。
    必要な環境変数：
      GRB_WLSACCESSID, GRB_WLSSECRET, GRB_LICENSEID

    例（PowerShell）：
      setx GRB_WLSACCESSID "xxxx"
      setx GRB_WLSSECRET   "yyyy"
      setx GRB_LICENSEID   "zzzz"
    """
    access_id = os.getenv("GRB_WLSACCESSID")
    secret = os.getenv("GRB_WLSSECRET")
    lic = os.getenv("GRB_LICENSEID")

    if not access_id or not secret or not lic:
        raise RuntimeError(
            "Gurobi WLSの環境変数が未設定です。"
            "GRB_WLSACCESSID, GRB_WLSSECRET, GRB_LICENSEID を設定してください。"
        )

    env = gp.Env(empty=True)
    env.setParam("WLSAccessID", access_id)
    env.setParam("WLSSecret", secret)
    env.setParam("LicenseID", int(lic))
    env.start()
    return env


# =========================
# メイン
# =========================
def solve_one_case(
    run_dir: Path,
    lambda_t: list[float],
    R_b: list[float],
    R2_b: list[float],
    S_mat,
    T_mat,
    S10_mat,
    T10_mat,
    fix_k0: bool,
    fix_k1: bool,
    fix_k2: bool,
) -> dict:
    # ==========
    # 定数
    # ==========
    alpha = 0.5
    f = 0.95
    p = 1.0
    p2 = 1.0
    delta_t = 0.5
    B_const = 1000
    D = 100 * B_const / 0.2  # 元コードに合わせて残す（未使用でも保持）
    T = range(48)
    T_q = range(49)
    B = range(8)
    I = range(10)
    I2 = range(4)
    J2 = range(4)
    N2 = range(1, 4)
    R3 = range(3)

    F = range(1, 10)
    F2 = range(2, 10)
    F3 = range(9)
    F4 = range(1, 11)
    F5 = range(10)

    r = 11
    n = 1
    k = 0.1
    c = 0.5 * (1 / 0.2) * 1000 * 29

    # i2, j2 = 4として明示（元コードの意図を維持，未使用でも保持）
    i2, j2 = 4, 4

    # ==========
    # Gurobi環境
    # ==========
    env = build_gurobi_env()

    # ==========
    # モデル作成
    # ==========
    model = Model("full_model", env=env)

    # 変数定義
    k0 = model.addVars(T_q, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k0")
    k1 = model.addVars(T_q, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k1")
    k2 = model.addVars(T_q, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k2")

    Qr = model.addVars(T_q, vtype=GRB.CONTINUOUS, name="Qr")
    Qr2 = model.addVars(T_q, vtype=GRB.CONTINUOUS, name="Qr2")
    Qs = model.addVars(T_q, lb=0, vtype=GRB.CONTINUOUS, name="Qs")

    P_buy = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="P_buy")
    P_sel = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="P_sel")
    a = model.addVars(T, vtype=GRB.BINARY, name="a")

    delta_kW = model.addVars(B, lb=0, vtype=GRB.CONTINUOUS, name="delta_kW")
    delta_kW2 = model.addVars(B, lb=0, vtype=GRB.CONTINUOUS, name="delta_kW2")

    x = model.addVars(T, I, lb=0, vtype=GRB.CONTINUOUS, name="x")
    z = model.addVars(T, I, vtype=GRB.BINARY, name="z")

    # 新しい変数定義
    U = model.addVars(r, T, vtype=GRB.BINARY, name="U")                  # U[i, t]
    W = model.addVars([1, 2], r, T, lb=0, vtype=GRB.BINARY, name="W")    # W[l, i, t]
    Z2 = model.addVars(F, [0], T, vtype=GRB.BINARY, name="Z2")           # Z2[l, i, t]
    Z3 = model.addVars(F, [0], T, vtype=GRB.BINARY, name="Z3")           # Z3[l, i, t]

    x2 = model.addVars(F4, F4, T, lb=0, vtype=GRB.CONTINUOUS, name="x2")
    y2 = model.addVars(F4, F4, T, lb=0, vtype=GRB.CONTINUOUS, name="y2")

    W2 = model.addVars(F, F5, T, lb=0, vtype=GRB.BINARY, name="W2")
    A = model.addVars(F4, F4, T, lb=0, vtype=GRB.BINARY, name="A")

    # L定義（元コードどおり 1..10 を使うため length=11）
    L = [1 / 10] * 11

    # ==========
    # 制約
    # ==========
    # k0 + k1 + k2 = 1
    for t in T_q:
        model.addConstr(k0[t] + k1[t] + k2[t] == 1)
        if fix_k0:
            model.addConstr(k0[t] == 0)
        if fix_k1:
            model.addConstr(k1[t] == 0)
        if fix_k2:
            model.addConstr(k2[t] == 0)

    # 初期・終端制約
    model.addConstr(Qr[0] + Qs[0] + Qr2[0] == Qr[48] + Qs[48] + Qr2[48])
    model.addConstr(Qr[0] + Qs[0] + Qr2[0] == 0.5 * B_const)

    for t in T:
        model.addConstr(Qr[t] + Qs[t] + Qr2[t] <= 1.0 * B_const)
        model.addConstr(Qr[t] + Qs[t] + Qr2[t] >= 0.1 * B_const)

    # Qr 再帰制約
    for t in T:
        b = t // 6
        delta_kWh = p * delta_kW[b] * delta_t
        rhs = f * (1 - alpha) * delta_kWh - (alpha / (f * f)) * delta_kWh
        model.addConstr(Qr[t + 1] == Qr[t] + rhs)

    # Qr2 再帰制約
    for t in T:
        b = t // 6
        delta_kWh2 = p2 * delta_kW2[b] * delta_t
        rhs2 = f * (1 - alpha) * delta_kWh2 - (alpha / (f * f)) * delta_kWh2
        model.addConstr(Qr2[t + 1] == Qr2[t] + rhs2)

    # Qr, Qr2, Qs <= B制約
    for t in T_q:
        if t < 48:
            model.addConstr(Qr[t] <= B_const * k1[t])
            model.addConstr(Qr2[t] <= B_const * k2[t])
            model.addConstr(Qs[t] <= B_const * k0[t])
        else:
            model.addConstr(Qr[t] <= B_const * k1[47])
            model.addConstr(Qr2[t] <= B_const * k2[47])
            model.addConstr(Qs[t] <= B_const * k0[47])

    # P_buy, P_sel 制約
    for t in T:
        model.addConstr(P_buy[t] <= B_const * a[t])
        model.addConstr(P_sel[t] <= B_const * (1 - a[t]))

    # Qs 再帰
    for t in T:
        rhs = f * P_buy[t] - P_sel[t] / (f * f)
        model.addConstr(Qs[t + 1] == Qs[t] + rhs)

    # xの合計制約
    for t in T:
        b = t // 6
        rhs = (P_sel[t] + alpha * p * delta_kW[b] * delta_t + alpha * p2 * delta_kW2[b] * delta_t) / (B_const * f * f)
        model.addConstr(sum(x[t, i] for i in I) == rhs)

    # Qr, Qr2 に ΔkWh に基づく上下限制約（t=1..47）
    for t in list(T)[1:]:
        b = t // 6
        delta_kWh = p * delta_kW[b] * delta_t
        lower_qr = (alpha / (f * f)) * delta_kWh
        upper_qr = B_const * k1[t] - f * (1 - alpha) * delta_kWh
        model.addConstr(Qr[t - 1] >= lower_qr)
        model.addConstr(Qr[t - 1] <= upper_qr)

        delta_kWh2 = p2 * delta_kW2[b] * delta_t
        lower_qr2 = (alpha / (f * f)) * delta_kWh2
        upper_qr2 = B_const * k2[t] - f * (1 - alpha) * delta_kWh2
        model.addConstr(Qr2[t - 1] >= lower_qr2)
        model.addConstr(Qr2[t - 1] <= upper_qr2)

    # Uの初期値制約と合計制約（元コード準拠）
    for t in T:
        model.addConstr(sum(U[i, t] for i in N2) == 1, name=f"U_sum_to_1_t{t}")

    # (1) W2 = AND(Z2[i], U[j])  for i=1..9, j=1..10 -> j0=j-1
    for t in T:
        for j0 in F5:
            j = j0 + 1
            for i in F:
                model.addConstr(0 <= Z2[i, 0, t] + U[j, t] - 2 * W2[i, j0, t])
                model.addConstr(Z2[i, 0, t] + U[j, t] - 2 * W2[i, j0, t] <= 1)

    # (2) x2 constraints
    for t in T:
        for j0 in F5:
            j = j0 + 1

            # i = 1
            model.addConstr(L[1] * W2[1, j0, t] <= x2[1, j, t])
            model.addConstr(x2[1, j, t] <= L[1] * U[j, t])

            # i = 2..9
            for i in F2:
                model.addConstr(L[i] * W2[i, j0, t] <= x2[i, j, t])
                model.addConstr(x2[i, j, t] <= L[i] * W2[i - 1, j0, t])

            # i = 10
            model.addConstr(0 <= x2[10, j, t])
            model.addConstr(x2[10, j, t] <= L[10] * W2[9, j0, t])

    # (3) Z3 (Z') definitions: i=1..9 only
    for t in T:
        model.addConstr(Z3[1, 0, t] == 1 - Z2[1, 0, t])
        for i in F2:
            model.addConstr(0 <= Z2[i - 1, 0, t] + (1 - Z2[i, 0, t]) - 2 * Z3[i, 0, t])
            model.addConstr(Z2[i - 1, 0, t] + (1 - Z2[i, 0, t]) - 2 * Z3[i, 0, t] <= 1)

    # (4) A[i,j,t]
    for t in T:
        # i=1..9: AND(Z3[i], U[j])
        for i in F:
            for j in F4:
                model.addConstr(0 <= Z3[i, 0, t] + U[j, t] - 2 * A[i, j, t])
                model.addConstr(Z3[i, 0, t] + U[j, t] - 2 * A[i, j, t] <= 1)

        # i=10: AND(Z2[9], U[j])
        for j in F4:
            model.addConstr(0 <= Z2[9, 0, t] + U[j, t] - 2 * A[10, j, t])
            model.addConstr(Z2[9, 0, t] + U[j, t] - 2 * A[10, j, t] <= 1)

    # U one-hot
    for t in T:
        model.addConstr(gp.quicksum(U[j, t] for j in F4) == 1)

    # 各 i で A 行和 = Z3 or Z2[9]
    for t in T:
        for i in F:
            model.addConstr(gp.quicksum(A[i, j, t] for j in F4) == Z3[i, 0, t])
        model.addConstr(gp.quicksum(A[10, j, t] for j in F4) == Z2[9, 0, t])

    # (5) y2 階段制約
    r_local = 11
    for t in T:
        for i in F4:
            for j in F:
                model.addConstr(
                    L[j] * gp.quicksum(A[i, k, t] for k in range(j + 1, r_local)) <= y2[i, j, t]
                )
                model.addConstr(
                    y2[i, j, t] <= L[j] * gp.quicksum(A[i, k, t] for k in range(j, r_local))
                )
            model.addConstr(0 <= y2[i, 10, t])
            model.addConstr(y2[i, 10, t] <= L[10] * A[i, 10, t])

    # Σx2, Σy2
    for t in T:
        b = t // 6
        delta_kWh = p * delta_kW[b] * delta_t
        delta_kWh2 = p2 * delta_kW2[b] * delta_t

        model.addConstr(
            sum(x2[i, j, t] for i in F4 for j in F4) == (Qs[t] + Qr[t] + Qr2[t]) / B_const,
            name=f"sum_x2_constraint_t{t}",
        )
        model.addConstr(
            sum(y2[i, j, t] for i in F4 for j in F4)
            == (P_sel[t] + alpha * delta_kWh + alpha * delta_kWh2) / (B_const * f * f),
            name=f"sum_y2_constraint_t{t}",
        )

    # ==========
    # パラメータ
    # ==========
    model.setParam("MIPGap", 1e-6)
    model.setParam("FeasibilityTol", 1e-9)
    model.setParam("IntFeasTol", 1e-9)

    # ==========
    # 目的関数
    # ==========
    expr = (
        # A
        sum(lambda_t[t] * (P_buy[t] - P_sel[t]) for t in T)
        # B
        - sum(6 * R_b[b] * delta_kW[b] for b in B)
        # C
        - sum(6 * R2_b[b] * delta_kW2[b] for b in B)
        # D
        + sum(
            (S10_mat[i][j] * x2[i, j, t] + T10_mat[i][j] * y2[i, j, t]) * c
            for i in range(1, len(S10_mat))
            for j in range(1, len(S10_mat[0]))
            for t in T
        )
        # E（元コードの追加項，そのまま維持）
        - sum(
            lambda_t[t]
            * (p * delta_kW[t // 6] * delta_t + p2 * delta_kW2[t // 6] * delta_t)
            * k
            for t in T
        )
    )

    model.setObjective(expr, GRB.MINIMIZE)

    # ==========
    # 最適化
    # ==========
    model.optimize()

    # --- Qs+Qr+Qr2（SOC分子）を出力 ---
    print("[DEBUG] Energy = Qs[t] + Qr[t] + Qr2[t] (t=0..48)")
    for t in T_q:  # T_q = range(49)
        energy = Qs[t].X + Qr[t].X + Qr2[t].X
        print(f"t={t:02d} energy={energy:.8f}  (Qs={Qs[t].X:.8f}, Qr={Qr[t].X:.8f}, Qr2={Qr2[t].X:.8f})")

    # --- Qsのrhs（更新量）を全部表示（t=0..47）---
    print("[DEBUG] Qs rhs per t (rhs = f*P_buy[t] - P_sel[t]/(f*f))")
    print("t  rhs            Qs[t]          Qs[t+1]        check_diff      P_buy         P_sel")
    for t in T:  # T = range(48)
        pb = P_buy[t].X
        ps = P_sel[t].X
        rhs = f * pb - ps / (f * f)

        qs_t = Qs[t].X
        qs_tp1 = Qs[t + 1].X
        diff = qs_tp1 - (qs_t + rhs)

        print(
            f"{t:02d} {rhs:14.10f} "
            f"{qs_t:14.6f} {qs_tp1:14.6f} {diff: .3e} "
            f"{pb:12.6f} {ps:12.6f}"
        )


        # --- Qrのrhsを t=47 で確認 ---
    t = 47
    b = t // 6  # 7
    delta_kWh = p * delta_kW[b].X * delta_t

    rhs_47 = f * (1 - alpha) * delta_kWh - (alpha / (f * f)) * delta_kWh

    print("[DEBUG] Qr rhs at t=47")
    print(f"  b={b}")
    print(f"  delta_kW[b]={delta_kW[b].X}")
    print(f"  delta_t={delta_t}")
    print(f"  delta_kWh={delta_kWh}")
    print(f"  rhs_47={rhs_47}")

    # --- delta_kW を全部表示（Qrで参照している値） ---
    print("[DEBUG] delta_kW[b] for b in B (used in Qr update)")
    for b in B:  # B = range(8)
        print(f"  b={b}: delta_kW={delta_kW[b].X}")

    # --- Qr / delta_kW / rhs を全部表示（t=0..47）---
    print("[DEBUG] Qr recursion detail per t")
    print("t  b  delta_kW        delta_kWh       rhs            Qr[t]          Qr[t+1]        check_diff")
    for t in T:  # T = range(48)
        b = t // 6
        dkW = delta_kW[b].X
        delta_kWh = p * dkW * delta_t
        rhs = f * (1 - alpha) * delta_kWh - (alpha / (f * f)) * delta_kWh

        qr_t = Qr[t].X
        qr_tp1 = Qr[t + 1].X
        diff = qr_tp1 - (qr_t + rhs)

        print(
            f"{t:02d} {b:1d} "
            f"{dkW:14.10f} {delta_kWh:14.10f} {rhs:14.10f} "
            f"{qr_t:14.6f} {qr_tp1:14.6f} {diff: .3e}"
        )


    # ==========
    # 出力（保存先をrun_dirに統一）
    # ==========
    if model.status != GRB.OPTIMAL:
        print("最適解が得られませんでした。")
        return {
            "status": int(model.status),
            "status_name": "NOT_OPTIMAL",
            "objVal": None,
            "runtime": float(getattr(model, "Runtime", float("nan"))),
        }

    # --- x2, y2（非ゼロのみ）をテキスト保存 ---
    x2_txt = run_dir / "x2_nonzero.txt"
    y2_txt = run_dir / "y2_nonzero.txt"

    with x2_txt.open("w", encoding="utf-8") as f_out:
        f_out.write("--- x2[i][j][t] nonzero ---\n")
        for i in F4:
            for j in F4:
                for t in T:
                    val = x2[i, j, t].X
                    if abs(val) > 1e-6:
                        f_out.write(f"x2[{i}][{j}][{t}] = {val:.8f}\n")

    with y2_txt.open("w", encoding="utf-8") as f_out:
        f_out.write("--- y2[i][j][t] nonzero ---\n")
        for i in F4:
            for j in F4:
                for t in T:
                    val = y2[i, j, t].X
                    if abs(val) > 1e-6:
                        f_out.write(f"y2[{i}][{j}][{t}] = {val:.8f}\n")

    print(f"[SAVE] {x2_txt}")
    print(f"[SAVE] {y2_txt}")

    # --- U, Z2, W2, Aのログ保存 ---
    log_txt = run_dir / "binary_logs.txt"
    with log_txt.open("w", encoding="utf-8") as f_out:
        f_out.write("--- U[i][t] ---\n")
        for t in T:
            line = ", ".join([f"U[{i},{t}]={U[i, t].X:.0f}" for i in range(r)])
            f_out.write(line + "\n")

        f_out.write("\n--- Z2[i][0][t] ---\n")
        for t in T:
            line = ", ".join([f"Z2[{i},0,{t}]={Z2[i, 0, t].X:.0f}" for i in F])
            f_out.write(line + "\n")

        f_out.write("\n--- W2[i][j0][t] ---\n")
        for t in T:
            items = []
            for i in F:
                for j0 in F5:
                    v = W2[i, j0, t].X
                    if abs(v) > 1e-6:
                        items.append(f"W2[{i},{j0},{t}]={v:.0f}")
            if items:
                f_out.write(", ".join(items) + "\n")

        f_out.write("\n--- A[i][j][t] nonzero ---\n")
        for t in T:
            items = []
            for i in F4:
                for j in F4:
                    v = A[i, j, t].X
                    if abs(v) > 1e-6:
                        items.append(f"A[{i},{j},{t}]={v:.0f}")
            if items:
                f_out.write(", ".join(items) + "\n")

    print(f"[SAVE] {log_txt}")



    # --- SOC計算（t=0..48）をCSV保存 ---
    soc = []
    for t in T_q:
        val = (Qs[t].X + Qr[t].X + Qr2[t].X) / B_const
        soc.append(val)

    soc_csv = run_dir / "soc_2d.csv"
    np.savetxt(soc_csv, np.array(soc), delimiter=",")
    print(f"[SAVE] {soc_csv}")

    # --- 目的関数の成分 A,B,C,D（t=0..47） ---
    A_vals, B_vals, C_vals, D_vals = [], [], [], []
    for t in T:
        b = t // 6

        A_t = lambda_t[t] * (P_buy[t].X - P_sel[t].X)

        delta_kWh = p * delta_kW[b].X * delta_t
        delta_kWh2 = p2 * delta_kW2[b].X * delta_t

        # 元コードの「EをB,Cに分けた」表現を維持
        B_t = -(6 * R_b[b] * delta_kW[b].X) / 6 - lambda_t[t] * delta_kWh * k
        C_t = -(6 * R2_b[b] * delta_kW2[b].X) / 6 - lambda_t[t] * delta_kWh2 * k

        D_t = 0.0
        for i in range(1, len(S10_mat)):
            for j in range(1, len(S10_mat[0])):
                D_t += (S10_mat[i][j] * x2[i, j, t].X + T10_mat[i][j] * y2[i, j, t].X) * c

        A_vals.append(A_t)
        B_vals.append(B_t)
        C_vals.append(C_t)
        D_vals.append(D_t)

    comp_csv = run_dir / "objective_components_ABCD.csv"
    comp_df = pd.DataFrame(
        {"t": list(T), "A": A_vals, "B": B_vals, "C": C_vals, "D": D_vals}
    )

    # 先頭に総和行を追加（ヘッダ直下の1行目）
    total_row = pd.DataFrame([{
        "t": "TOTAL",
        "A": float(np.sum(A_vals)),
        "B": float(np.sum(B_vals)),
        "C": float(np.sum(C_vals)),
        "D": float(np.sum(D_vals)),
    }])

    comp_df_out = pd.concat([total_row, comp_df], ignore_index=True)

    comp_df_out.to_csv(comp_csv, index=False, encoding="utf-8-sig")

    print(f"[SAVE] {comp_csv}")

    # --- 積み上げ棒グラフ（正負分離）を保存 ---
    A_arr = np.array(A_vals)
    B_arr = np.array(B_vals)
    C_arr = np.array(C_vals)
    D_arr = np.array(D_vals)

    x_axis = np.arange(len(A_arr))  # 0..47

    A_pos = np.where(A_arr > 0, A_arr, 0.0)
    B_pos = np.where(B_arr > 0, B_arr, 0.0)
    C_pos = np.where(C_arr > 0, C_arr, 0.0)
    D_pos = np.where(D_arr > 0, D_arr, 0.0)

    A_neg = np.where(A_arr < 0, A_arr, 0.0)
    B_neg = np.where(B_arr < 0, B_arr, 0.0)
    C_neg = np.where(C_arr < 0, C_arr, 0.0)
    D_neg = np.where(D_arr < 0, D_arr, 0.0)

    bottom_pos_A = np.zeros_like(A_arr)
    bottom_pos_B = A_pos
    bottom_pos_C = A_pos + B_pos
    bottom_pos_D = A_pos + B_pos + C_pos

    bottom_neg_A = np.zeros_like(A_arr)
    bottom_neg_B = A_neg
    bottom_neg_C = A_neg + B_neg
    bottom_neg_D = A_neg + B_neg + C_neg

    plt.figure(figsize=(16, 6))
    color_A, color_B, color_C, color_D = "C0", "C1", "C2", "C3"

    plt.bar(x_axis, A_pos, bottom=bottom_pos_A, color=color_A, label="A")
    plt.bar(x_axis, B_pos, bottom=bottom_pos_B, color=color_B, label="B")
    plt.bar(x_axis, C_pos, bottom=bottom_pos_C, color=color_C, label="C")
    plt.bar(x_axis, D_pos, bottom=bottom_pos_D, color=color_D, label="D")

    plt.bar(x_axis, A_neg, bottom=bottom_neg_A, color=color_A)
    plt.bar(x_axis, B_neg, bottom=bottom_neg_B, color=color_B)
    plt.bar(x_axis, C_neg, bottom=bottom_neg_C, color=color_C)
    plt.bar(x_axis, D_neg, bottom=bottom_neg_D, color=color_D)

    plt.axhline(0, linewidth=1)
    plt.xticks(x_axis, [str(t) for t in range(len(A_arr))], rotation=90)
    plt.xlabel("t")
    plt.ylabel("Objective components (stacked, pos/neg)")
    plt.title("Stacked objective components A, B, C, D (t = 0..47)")

    plt.ylim(-20000, 10000)
    plt.gca().invert_yaxis()

    plt.legend(ncol=4)
    plt.tight_layout()

    fig1_path = run_dir / "stacked_objective_ABCD.png"
    plt.savefig(fig1_path, dpi=200)
    plt.close()
    print(f"[SAVE] {fig1_path}")

    # --- SOCと市場価格の2軸プロットを保存 ---
    price = lambda_t  # 0..47
    ts_soc = list(range(49))
    ts_price = list(range(48))

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(ts_soc, soc, marker="o", color="tab:orange", label="SOC = (Qs+Qr+Qr2)/B_const")
    ax1.set_xlabel("t")
    ax1.set_ylabel("SOC")

    ax2 = ax1.twinx()
    ax2.plot(ts_price, [price[t] for t in ts_price], marker="x", linestyle="--", label="Market price (spot6)")
    ax2.set_ylabel("Price")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    plt.title("SOC and market price (spot6) over time")
    plt.tight_layout()

    fig2_path = run_dir / "soc_and_price.png"
    plt.savefig(fig2_path, dpi=200)
    plt.close()
    print(f"[SAVE] {fig2_path}")

    print("[DONE] 完了しました。")


        # ===== 総劣化（劣化項）だけ算出して最後に表示 =====
    total_deg_cost = 0.0
    for t in T:
        for i in range(1, len(S10_mat)):
            for j in range(1, len(S10_mat[0])):
                total_deg_cost += (S10_mat[i][j] * x2[i, j, t].X + T10_mat[i][j] * y2[i, j, t].X) * c

    # 目的関数値（Gurobiの目的）を保存：数値だけ
    obj_val = float(model.ObjVal)
    obj_txt = run_dir / "objective_value.txt"
    obj_txt.write_text(f"{obj_val:.10f}\n", encoding="utf-8")
    print(f"[SAVE] {obj_txt}")

    # k0,k1,k2 と SOC を DataFrame 化（Excel集計用）
    k_df = pd.DataFrame({
        "t": list(T_q),
        "k0": [k0[t].X for t in T_q],
        "k1": [k1[t].X for t in T_q],
        "k2": [k2[t].X for t in T_q],
    })
    soc_df = pd.DataFrame({"t": list(T_q), "soc": soc})

    totals = {
        "A_total": float(np.sum(A_vals)),
        "B_total": float(np.sum(B_vals)),
        "C_total": float(np.sum(C_vals)),
        "D_total": float(np.sum(D_vals)),
    }

    return {
        "status": int(model.status),
        "status_name": "OPTIMAL",
        "objVal": obj_val,
        "runtime": float(getattr(model, "Runtime", float("nan"))),
        "total_deg_cost": float(total_deg_cost),
        **totals,
        "k_df": k_df,
        "soc_df": soc_df,
    }



def main() -> None:
    run_root = make_run_dir(prefix="2d_piecewise_batch")
    print(f"[INFO] run_root = {run_root}")

    # ==========
    # 入力Excel
    # ==========
    data5_path = EXCEL_DIR / "Data5.xlsx"
    cycle_path = EXCEL_DIR / "0704サイクル劣化.xlsx"

    if not data5_path.exists():
        raise FileNotFoundError(f"入力が見つかりません: {data5_path}")
    if not cycle_path.exists():
        raise FileNotFoundError(f"入力が見つかりません: {cycle_path}")

    # ExcelからλとRを読み込む
    df = pd.read_excel(data5_path, sheet_name=0)
    lambda_t = df["spot6"].tolist()[:48]
    R_b = df["pri6"].dropna().tolist()[:8]
    R2_b = df["sec6"].dropna().tolist()[:8]
    _ = df["Sdata"].dropna().tolist()[:10]  # 元コードに合わせて残す（未使用でも読み込みは維持）

    df_s = pd.read_excel(cycle_path, sheet_name="s", header=None, usecols=range(4), nrows=4)
    df_t = pd.read_excel(cycle_path, sheet_name="t", header=None, usecols=range(4), nrows=4)
    df_s10 = pd.read_excel(cycle_path, sheet_name="s10", header=None, usecols=range(10), nrows=10)
    df_t10 = pd.read_excel(cycle_path, sheet_name="t10", header=None, usecols=range(10), nrows=10)

    S_mat = df_s.values.tolist()     # 4×4
    T_mat = df_t.values.tolist()     # 4×4
    S10_mat = df_s10                 # 10×10（DataFrameのまま）
    T10_mat = df_t10                 # 10×10（DataFrameのまま）

    # ==========
    # 7通り（k0,k1,k2 の ==0 制約を適用/しない の 2^3 から，全適用を除外）
    # ==========
    cases: list[tuple[bool, bool, bool]] = []
    for fix_k0, fix_k1, fix_k2 in itertools.product([False, True], repeat=3):
        if fix_k0 and fix_k1 and fix_k2:
            continue
        cases.append((fix_k0, fix_k1, fix_k2))

    results: list[dict] = []

    def _tag(fix: bool) -> str:
        return "Z" if fix else "F"  # Z: zero固定（==0）, F: free

    for idx, (fix_k0, fix_k1, fix_k2) in enumerate(cases, start=1):
        label = f"k0{_tag(fix_k0)}k1{_tag(fix_k1)}k2{_tag(fix_k2)}"
        case_id = f"c{idx:02d}"
        case_dir = run_root / f"{case_id}_{label}"
        case_dir.mkdir(parents=True, exist_ok=True)

        res = solve_one_case(
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

        res.update({
            "case_id": case_id,
            "label": label,
            "fix_k0": fix_k0,
            "fix_k1": fix_k1,
            "fix_k2": fix_k2,
            "case_dir": str(case_dir),
            "sheet": f"{case_id}_{label}"[:31],  # Excelのシート名制限
        })
        results.append(res)

    # ==========
    # Excel出力（集計）
    # ==========
    xlsx_path = run_root / "batch_results.xlsx"

    summary_rows = []
    for r in results:
        row = {k: v for k, v in r.items() if k not in ("k_df", "soc_df")}
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)

        for r in results:
            sheet = r.get("sheet", "case")[:31]

            # k0,k1,k2
            k_df = r.get("k_df")
            if isinstance(k_df, pd.DataFrame):
                k_df.to_excel(writer, sheet_name=sheet, index=False, startrow=0)
                next_row = len(k_df) + 2
            else:
                next_row = 0

            # SOC
            soc_df = r.get("soc_df")
            if isinstance(soc_df, pd.DataFrame):
                soc_df.to_excel(writer, sheet_name=sheet, index=False, startrow=next_row)

    print(f"[SAVE] {xlsx_path}")


if __name__ == "__main__":
    main()
