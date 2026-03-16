
import pandas as pd
from gurobipy import Model, GRB

# ExcelからλとRを読み込む
data_path = r"C:\Users\tam1015\Desktop\kitano\Data5.xlsx"
df = pd.read_excel(data_path, sheet_name=0)

lambda_t = df['spot6'].tolist()[:48]
R_b = df['pri6'].dropna().tolist()[:8]
R2_b = df['sec6'].dropna().tolist()[:8]
S = df['Sdata'].dropna().tolist()[:10]

# 定数
alpha = 0.5
f = 0.95
p = 1.0
p2 = 1.0
delta_t = 0.5
B_const = 1000
D = 10 * B_const / 0.2
T = range(48)
T_q = range(49)
B = range(8)
I = range(10)

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

# 目的関数
expr = (
    sum(lambda_t[t] * (P_buy[t] - P_sel[t]) for t in T)
    - sum(6 * R_b[b] * delta_kW[b] for b in B)
    - sum(6 * R2_b[b] * delta_kW2[b] for b in B)
    + sum(D * x[t, i] * S[i] for t in T for i in I)
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
else:
    print("最適解が見つかりませんでした。")
