import pandas as pd
from gurobipy import Model, GRB

# ExcelからλとRを読み込む
data_path = "C:/Users/tam1015/Desktop/kitano/Data4.xlsx"
df = pd.read_excel(data_path, sheet_name=0)

lambda_t = df['spot5'].tolist()[:48]
R_b = df['pri5'].dropna().tolist()[:8]
R2_b = df['sec5'].dropna().tolist()[:8]

# 定数
alpha = 0.5
f = 0.95
p = 1.0
p2 = 1.0
delta_t = 0.5
B_const = 40
T = range(48)
T_q = range(49)
B = range(8)

# モデル作成
model = Model("full_model")

# 変数定義
k0 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k0")
k1 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k1")
k2 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k2")
Qr = model.addVars(T_q, vtype=GRB.CONTINUOUS, name="Qr")
Qr2 = model.addVars(T_q, vtype=GRB.CONTINUOUS, name="Qr2")
Qs = model.addVars(T_q, lb=0, vtype=GRB.CONTINUOUS, name="Qs")
x = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="x")
y = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="y")
a = model.addVars(T, vtype=GRB.BINARY, name="a")
delta_kW = model.addVars(B, lb=0, vtype=GRB.CONTINUOUS, name="delta_kW")
delta_kW2 = model.addVars(B, lb=0, vtype=GRB.CONTINUOUS, name="delta_kW2")

# k0 + k1 + k2 = 1（k2も含む）
for t in T:
    model.addConstr(k0[t] + k1[t] + k2[t] == 1)

# 初期・終端制約（エネルギー保存）
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

# x, y 制約
for t in T:
    model.addConstr(x[t] <= B_const * a[t])
    model.addConstr(y[t] <= B_const * (1 - a[t]))

# Qs 再帰
for t in T:
    rhs = f * x[t] - y[t] / (f * f)
    model.addConstr(Qs[t + 1] == Qs[t] + rhs)

# Qr2 に ΔkWh に基づく上下限制約を追加（t=1〜47）
for t in T[1:]:
    b = t // 6
    delta_kWh2 = p2 * delta_kW2[b] * delta_t
    lower = (alpha / (f * f)) * delta_kWh2
    upper = B_const * k2[t] - f * (1 - alpha) * delta_kWh2
    model.addConstr(Qr2[t - 1] >= lower)
    model.addConstr(Qr2[t - 1] <= upper)

# 目的関数
expr = (
    sum(lambda_t[t] * (x[t] - y[t]) for t in T)
    - sum(6 * R_b[b] * delta_kW[b] for b in B)
    - sum(6 * R2_b[b] * delta_kW2[b] for b in B)
)
model.setObjective(expr, GRB.MINIMIZE)

# 最適化
model.optimize()

# 出力
if model.status == GRB.OPTIMAL:
    print(f"目的関数値: {model.objVal:.3f}")
    for t in T_q:
        out = f"t={t:02d}, "
        if t < 48:
            out += f"k0={k0[t].X:.3f}, k1={k1[t].X:.3f}, k2={k2[t].X:.3f}, "
        out += f"Qr={Qr[t].X:.2f}, Qr2={Qr2[t].X:.2f}, Qs={Qs[t].X:.2f}"
        print(out)
    print("\nΔkW[b] の最適値:")
    for b in B:
        print(f"b={b}, ΔkW={delta_kW[b].X:.3f}, ΔkW2={delta_kW2[b].X:.3f}")
else:
    print("最適解が見つかりませんでした。")
