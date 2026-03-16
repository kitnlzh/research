
import pandas as pd
from gurobipy import Model, GRB

# ExcelからλとRを読み込む
data_path = r"C:\Users\tam1015\Desktop\kitano\Data5.xlsx"
df = pd.read_excel(data_path, sheet_name=0)

# s, t のシートを読み込み（4×4）
excel_path = r"C:\Users\kit02\OneDrive\研究\エクセル\0704サイクル劣化.xlsx"
df_s = pd.read_excel(excel_path, sheet_name="s", header=None, usecols=range(4), nrows=4)
df_t = pd.read_excel(excel_path, sheet_name="t", header=None, usecols=range(4), nrows=4)

S_mat = df_s.values.tolist()  # 4×4リスト
T_mat = df_t.values.tolist()  # 4×4リスト


lambda_t = df['spot5'].tolist()[:48]
R_b = df['pri5'].dropna().tolist()[:8]
R2_b = df['sec5'].dropna().tolist()[:8]
S = df['Sdata'].dropna().tolist()[:10]

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
i2 = range(4)
j2 = range(4)

# モデル作成
model = Model("full_model")

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
x2 = model.addVars(i2, j2, T ,lb=0, vtype=GRB.CONTINUOUS, name="x2")
y2 = model.addVars(i2, j2, T ,lb=0, vtype=GRB.CONTINUOUS, name="y2")
U2 = model.addVars(i2, vtype=GRB.BINARY, name="U2")
W2 = model.addVars(i2, j2, vtype=GRB.BINARY, name="W2")
Z2 = model.addVars(i2, j2, vtype=GRB.BINARY, name="Z2")
# L定義
L = [0.1 for _ in I]
L2 =[1/3 for _ in i2]

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



# Σx = (Qs[48] + Qr[48] + Qr2[48]) / B
model.addConstr(
    sum(x[i, j] for i in i2 for j in j2) == (Qs[48] + Qr[48] + Qr2[48]) / B_const,
    name="sum_x_constraint"
)

# Σy = (P_sel[47] + ΔkWh + ΔkWh2) / (B * f^2)
b = 47 // 6  # 最後のブロックインデックス
delta_kWh = p * delta_kW[b] * delta_t
delta_kWh2 = p2 * delta_kW2[b] * delta_t

model.addConstr(
    sum(y2[i, j, t] for i in i2 for j in j2 for t in T) == (P_sel[47] + delta_kWh + delta_kWh2) / (B_const * f * f),
    name="sum_y_constraint"
)

#W2[1][i] <= Z2[1][i]

for i in j2:
    model.addConstr(W2[1, i] <= Z2[1, i], name=f"W2[1,{i}]<=Z2[1,{i}]")

#W2[2][i] <= Z2[2][i]

for i in j2:
    model.addConstr(W2[2, i] <= Z2[2, i], name=f"W2[2,{i}]<=Z2[2,{i}]")

#W2[1][i] <= U2[i]

for i in j2:
    model.addConstr(W2[1, i] <= U2[i], name=f"W2[1,{i}]<=U2[1,{i}]")

#W2[2][i] <= U2[i]

for i in j2:
    model.addConstr(W2[2, i] <= U2[i], name=f"W2[2,{i}]<=U2[2,{i}]")

#W2[2][i] >= U2[i] + Z2[1][0] - 1

for i in j2:
    model.addConstr(W2[2, i] >= U2[i] + Z2[1, 0] - 1, name=f"W2[2,{i}]>=U2[2,{i}]+Z2[1,0]-1")

#W2[2][i] >= U2[i] + Z2[2][0] - 1

for i in j2:
    model.addConstr(W2[2, i] >= U2[i] + Z2[2, 0] - 1, name=f"W2[2,{i}]>=U2[2,{i}]+Z2[2,0]-1")

#x2 に関する範囲制約
for t in T:
    for i in j2:
        model.addConstr(L2[1] * W2[1, 0] <= x2[1, i, t], name=f"x2[1,{i}]>=L2[1]*W2[1,0]")
        model.addConstr(x2[1, i, t] <= L2[1] * U2[i], name=f"x2[1,{i}]<=L2[1]*U2[1,{i}]")

        model.addConstr(L2[2] * W2[2, 0] <= x2[2, i, t], name=f"x2[2,{i}]>=L2[2]*W2[2,0]")
        model.addConstr(x2[2, i, t] <= L2[1] * W2[1, i], name=f"x2[2,{i}]<=L2[1]*W2[1,{i}]")

        model.addConstr(x2[3, i, t] >= 0, name=f"x2[3,{i}]>=0")
        model.addConstr(x2[3, i, t] <= L2[3] * W2[2, i], name=f"x2[3,{i}]<=L2[3]*W2[2,{i}]")

#i >= 1 のとき x2[0][i] = U2[i]
for t in T:
    for i in j2:
        if i >= 1:
            model.addConstr(x2[0, i, t] == U2[i], name=f"x2[0,{i}]==U2[0,{i}]")

#L2[1]*(U2[2]+U2[3]) <= y2[i][1] <= L2[1]*(U2[1]+U2[2]+U2[3])
for t in T:
    for i in i2:
        model.addConstr(
            y2[i, 1, t] >= L2[1] * (U2[2] + U2[3]),
            name=f"y2[{i},1]_lower"
        )
        model.addConstr(
            y2[i, 1, t] <= L2[1] * (U2[1] + U2[2] + U2[3]),
            name=f"y2[{i},1]_upper"
        )

#L2[2]*U2[3] <= y2[i][2] <= L2[2]*(U2[2]+U2[3])
for t in T:
    for i in i2:
        model.addConstr(
            y2[i, 2, t] >= L2[2] * U2[3],
            name=f"y2[{i},2]_lower"
        )
        model.addConstr(
            y2[i, 2, t] <= L2[2] * (U2[2] + U2[3]),
            name=f"y2[{i},2]_upper"
        )

#0 <= y2[i][3] <= L2[3] * U2[3]
for t in T:
    for i in i2:
        model.addConstr(
            y2[i, 3, t] >= 0,
            name=f"y2[{i},3]_lower"
        )
        model.addConstr(
            y2[i, 3, t] <= L2[3] * U2[3],
            name=f"y2[{i},3]_upper"
        )

#y2[0][0] = 0

for t in T:
    model.addConstr(y2[0, 0, t] == 0, name="y2[0,0]_zero")

#i >= 1 のとき y2[0][i] = U2[0]
for t in T:
    for j in j2:
        if j >= 1:
            model.addConstr(y2[j, 0, t] == U2[i], name=f"y2[0,{j}]_eq_U2[{j}]")


# 目的関数
expr = (
    sum(lambda_t[t] * (P_buy[t] - P_sel[t]) for t in T)
    - sum(6 * R_b[b] * delta_kW[b] for b in B)
    - sum(6 * R2_b[b] * delta_kW2[b] for b in B)
    + sum((S_mat[i][j] * x2[i, j, t] + T_mat[i][j] * y2[i, j, t] for i in i2 for j in j2 for t in T))
)
model.setObjective(expr, GRB.MINIMIZE)

# 最適化
model.optimize()

# 出力
print("\n変数 x[i,j] の値:")
for t in T:
    for i in i2:
        for j in j2:
            print(f"x2[{i},{j}] = {x2[i, j, t].X:.4f}")

print("\n変数 y[i,j] の値:")
for t in T:
    for i in i2:
        for j in j2:
            print(f"y2[{i},{j}] = {y2[i, j, t].X:.4f}")

