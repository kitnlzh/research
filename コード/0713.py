
import pandas as pd
from gurobipy import Model, GRB

# ExcelからλとRを読み込む
data_path = r"C:\Users\tam1015\Desktop\kitano\Data5.xlsx"
df = pd.read_excel("Data5.xlsx", sheet_name=0)

lambda_t = df['spot5'].tolist()[:48]
R_b = df['pri5'].dropna().tolist()[:8]
R2_b = df['sec5'].dropna().tolist()[:8]
S = df['Sdata'].dropna().tolist()[:10]

df_s = pd.read_excel("0704サイクル劣化.xlsx", sheet_name="s", header=None, usecols=range(4), nrows=4)
df_t = pd.read_excel("0704サイクル劣化.xlsx", sheet_name="t", header=None, usecols=range(4), nrows=4)


S_mat = df_s.values.tolist()  # 4×4リスト
T_mat = df_t.values.tolist()  # 4×4リスト


# 定数
alpha = 0.5
f = 0.95
p = 1.0
p2 = 1.0
delta_t = 0.5
B_const = 1000
D = 100 * B_const / 0.2
T = range(48)
T_q = range(49)
B = range(8)
I = range(10)
I2 = range(4)
J2 = range(4)

# モデル作成
model = Model("full_model",env=env)

# 変数定義
k0 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k0")
k1 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k1")
k2 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k2")
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
U2 = model.addVars(4, lb=0, vtype=GRB.BINARY, name="U2")

W2 = model.addVars([1, 2], 4, lb=0, vtype=GRB.CONTINUOUS, name="W2")
Z2 = model.addVars([1, 2], 4, vtype=GRB.BINARY, name="Z2")

L2 = [1/3 for _ in range(3)]  # 1~3をインデックスとするなら L2[1], L2[2], L2[3] を使うように注意

T = range(48)  # 既に定義済みであれば再定義不要

x2 = model.addVars(4, 4, T, lb=0, vtype=GRB.CONTINUOUS, name="x2")
y2 = model.addVars(4, 4, T, lb=0, vtype=GRB.CONTINUOUS, name="y2")


# L定義
L = [0.1 for _ in I]


# k0 + k1 + k2 = 1
for t in T:
    model.addConstr(k0[t] + k1[t] + k2[t] == 1)

# 初期・終端制約
model.addConstr(Qr[0] + Qs[0] + Qr2[0] == Qr[48] + Qs[48] + Qr2[48])

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
        model.addConstr(Qr[t] <= B_const)
        model.addConstr(Qr2[t] <= B_const)
        model.addConstr(Qs[t] <= B_const)

# P_buy, P_sel 制約
for t in T:
    model.addConstr(P_buy[t] <= B_const * a[t])
    model.addConstr(P_sel[t] <= B_const * (1 - a[t]))

# Qs 再帰
for t in T:
    rhs = f * P_buy[t] - P_sel[t] / (f * f)
    model.addConstr(Qs[t + 1] == Qs[t] + rhs)

# x-z関係の制約
for t in T:
    for i in I:
        if i == 0:
            model.addConstr(x[t, i] >= L[i] * z[t, i])
            model.addConstr(x[t, i] <= L[i])
        elif i == 9:
            model.addConstr(x[t, i] >= 0)
            model.addConstr(x[t, i] <= L[i] * z[t, i - 1])
        else:
            model.addConstr(x[t, i] >= L[i] * z[t, i])
            model.addConstr(x[t, i] <= L[i] * z[t, i - 1])

# xの合計制約
for t in T:
    b = t // 6
    rhs = (P_sel[t] + alpha * p * delta_kW[b] * delta_t + alpha * p2 * delta_kW2[b] * delta_t) / (B_const * f * f)
    model.addConstr(sum(x[t, i] for i in I) == rhs)

# Qr, Qr2 に ΔkWh に基づく上下限制約を追加（t=1〜47）
for t in T[1:]:
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


#U2[0]+U2[1]+U2[2]+U2[3]=1
model.addConstr(
    U2[0] + U2[1] + U2[2] + U2[3] == 1,
    name="U2_sum_to_1"
)


i2 = 3
j2 = 3

for i in range(i2):
    # W2[1][i] に関する制約
    model.addConstr(W2[1, i] <= Z2[1, i], name=f"W2_1_leq_Z2_1_{i}")
    model.addConstr(W2[1, i] <= U2[i], name=f"W2_1_leq_U2_{i}")
    model.addConstr(W2[1, i] >= Z2[1, i] + U2[i] - 1, name=f"W2_1_geq_logic_and_{i}")

    # W2[2][i] に関する制約
    model.addConstr(W2[2, i] <= Z2[2, i], name=f"W2_2_leq_Z2_2_{i}")
    model.addConstr(W2[2, i] <= U2[i], name=f"W2_2_leq_U2_{i}")
    model.addConstr(W2[2, i] >= Z2[2, i] + U2[2] - 1, name=f"W2_2_geq_logic_and_{i}")

    for t in T:
        # x2[1][i][t] の範囲制約
        model.addConstr(
            x2[1, i, t] >= L2[1] * W2[1, i],
            name=f"x2_1_{i}_{t}_geq"
        )
        model.addConstr(
            x2[1, i, t] <= L2[1] * U2[i],
            name=f"x2_1_{i}_{t}_leq"
        )

        # x2[2][i][t] の範囲制約
        model.addConstr(
            x2[2, i, t] >= L2[2] * W2[2, i],
            name=f"x2_2_{i}_{t}_geq"
        )
        model.addConstr(
            x2[2, i, t] <= L2[2] * W2[1, i],
            name=f"x2_2_{i}_{t}_leq"
        )

        # x2[3][i][t] の範囲制約
        model.addConstr(
            x2[3, i, t] >= 0,
            name=f"x2_3_{i}_{t}_geq"
        )
        model.addConstr(
            x2[3, i, t] <= L2[3] * W2[2, i],
            name=f"x2_3_{i}_{t}_leq"
        )

# i != 0 のとき、x2[0][i][t] = U2[i]
for i in range(1, i2):
    for t in T:
        model.addConstr(x2[0, i, t] == U2[i], name=f"x2_0_{i}_{t}_eq_U2_{i}")


for i in range(4):
    for t in T:
        # j=1: L2[1] * (U2[2] + U2[3]) <= y2[i][1][t] <= L2[1] * (U2[1] + U2[2] + U2[3])
        model.addConstr(
            y2[i, 1, t] >= L2[1] * (U2[2] + U2[3]),
            name=f"y2_{i}_1_{t}_geq"
        )
        model.addConstr(
            y2[i, 1, t] <= L2[1] * (U2[1] + U2[2] + U2[3]),
            name=f"y2_{i}_1_{t}_leq"
        )

        # j=2: L2[2] * U2[3] <= y2[i][2][t] <= L2[2] * (U2[2] + U2[3])
        model.addConstr(
            y2[i, 2, t] >= L2[2] * U2[3],
            name=f"y2_{i}_2_{t}_geq"
        )
        model.addConstr(
            y2[i, 2, t] <= L2[2] * (U2[2] + U2[3]),
            name=f"y2_{i}_2_{t}_leq"
        )

        # j=3: 0 <= y2[i][3][t] <= L2[3] * U2[3]
        model.addConstr(
            y2[i, 3, t] >= 0,
            name=f"y2_{i}_3_{t}_geq"
        )
        model.addConstr(
            y2[i, 3, t] <= L2[3] * U2[3],
            name=f"y2_{i}_3_{t}_leq"
        )

        # j=0 のときの特別制約
        if i == 0:
            model.addConstr(
                y2[i, 0, t] == 0,
                name=f"y2_{i}_0_{t}_eq_0"
            )
        else:
            model.addConstr(
                y2[i, 0, t] == U2[0],
                name=f"y2_{i}_0_{t}_eq_U2_0"
            )






for t in T:
    b = t // 6  # 6刻みの区切り

    # ΔkWhおよびΔkWh2
    delta_kWh = p * delta_kW[b] * delta_t
    delta_kWh2 = p2 * delta_kW2[b] * delta_t

    # Σx2 = (Qs + Qr + Qr2) / B
    model.addConstr(
        sum(x2[i, j, t] for i in range(4) for j in range(4)) == (Qs[t] + Qr[t] + Qr2[t]) / B_const,
        name=f"sum_x2_constraint_t{t}"
    )

    # Σy2 = (P_sel + ΔkWh + ΔkWh2) / (B * f^2)
    model.addConstr(
        sum(y2[i, j, t] for i in range(4) for j in range(4)) == (P_sel[t] + delta_kWh + delta_kWh2) / (B_const * f * f),
        name=f"sum_y2_constraint_t{t}"
    )


# 目的関数
expr = (
    sum(lambda_t[t] * (P_buy[t] - P_sel[t]) for t in T)
    - sum(6 * R_b[b] * delta_kW[b] for b in B)
    - sum(6 * R2_b[b] * delta_kW2[b] for b in B)
    + sum(S_mat[i,j]*x2[i,j,t]+T_mat[i,j]*y2[i,j,t] for i in I2 for j in J2 for t in T)
)
model.setObjective(expr, GRB.MINIMIZE)

# 最適化
model.optimize()

# 出力
if model.status == GRB.OPTIMAL:
    print("\nQr, Qr2, Qs の値:")
    for t in T_q:
        qr_val = Qr[t].X
        qr2_val = Qr2[t].X
        qs_val = Qs[t].X
        print(f"t={t:02d}, Qr={qr_val:.4f}, Qr2={qr2_val:.4f}, Qs={qs_val:.4f}")

    print(f"目的関数値: {model.objVal:.3f}")
    print("\n目的関数中の D * x[t,i] * S[i] の値:")
    total = 0
    for t in T:
        for i in I:
            val = D * x[t, i].X * S[i]
            total += val
            print(f"t={t:02d}, i={i}, D * x[t,i] * S[i] = {val:.4f}")
    print(f"\n合計値: {total:.4f}")

    print("\nk0, k1, k2 の値:")
    for t in T:
        print(f"t={t:02d}, k0={k0[t].X:.4f}, k1={k1[t].X:.4f}, k2={k2[t].X:.4f}")

    print("\nP_buy, P_sel, a の値:")
    for t in T:
        print(f"t={t:02d}, P_buy={P_buy[t].X:.4f}, P_sel={P_sel[t].X:.4f}, a={a[t].X:.0f}")

    print("\ndelta_kW, delta_kW2 の値:")
    for b in B:
        print(f"b={b}, delta_kW={delta_kW[b].X:.4f}, delta_kW2={delta_kW2[b].X:.4f}")
        print("\nz[t, i] のバイナリ値:")
    for t in T:
        for i in I:
            if (i!=9):
                print(f"t={t:02d}, i={i}, z={z[t, i].X:.0f}, x={x[t, i].X:.4f}")

    
else:
    print("最適解が見つかりませんでした。")
