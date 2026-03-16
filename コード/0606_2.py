import pandas as pd
from gurobipy import Model, GRB

# ExcelからλとRを読み込む（同じシート内にある想定）
data_path = "C:/Users/tam1015/Desktop/kitano/Data4.xlsx"
df = pd.read_excel(data_path, sheet_name=0)

lambda_t = df['date5'].tolist()[:48]  # 長さ48（0〜47）
R_b = df['pri'].dropna().tolist()[:8]  # 長さ8（0〜7）
R2_b = df['sec'].dropna().tolist()[:8]  # R2列も使用

# 定数
alpha = 0.5
f = 0.95
p = 1.0
p2 = 1.0
delta_t = 0.5
B_const = 40
T = range(48)
B = range(8)

# モデル作成
model = Model("full_model")

# 変数定義
k0 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k0")
k1 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k1")
k2 = model.addVars(T, lb=0, ub=1, vtype=GRB.CONTINUOUS, name="k2")
Qr = model.addVars(T, vtype=GRB.CONTINUOUS, name="Qr")
Qr2 = model.addVars(T, vtype=GRB.CONTINUOUS, name="Qr2")
Qs = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="Qs")
x = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="x")
y = model.addVars(T, lb=0, vtype=GRB.CONTINUOUS, name="y")
a = model.addVars(T, vtype=GRB.BINARY, name="a")
delta_kW = model.addVars(B, lb=0, vtype=GRB.CONTINUOUS, name="delta_kW")
delta_kW2 = model.addVars(B, lb=0, vtype=GRB.CONTINUOUS, name="delta_kW2")

# k0 + k1 + k2 = 1
for t in T:
    model.addConstr(k0[t] + k1[t] + k2[t] == 1)
    model.addConstr(k2[t] == 0)
    #model.addConstr(k1[t] == 0)

# Qr[0] = Qr[47]
#model.addConstr(Qs[0] == Qs[47])
#model.addConstr(Qr[0] == Qr[47])
#model.addConstr(Qr2[0] == Qr2[47])

model.addConstr(Qr[0] +Qs[0] == Qs[T] + Qr[T])

# Qr再帰制約
for t in T[:-1]:
    b = t // 6
    delta_kWh = p * delta_kW[b] * delta_t
    rhs = f * (1 - alpha) * delta_kWh - (alpha / (f * f)) * delta_kWh
    model.addConstr(Qr[t + 1] == Qr[t] + rhs)

# Qr2再帰制約
for t in T[:-1]:
    b = t // 6
    delta_kWh2 = p2 * delta_kW2[b] * delta_t
    rhs2 = f * (1 - alpha) * delta_kWh2 - (alpha / (f * f)) * delta_kWh2
    model.addConstr(Qr2[t + 1] == Qr2[t] + rhs2)

# Qr <= B*k1
for t in T:
    model.addConstr(Qr[t] <= B_const * k1[t])

# Qr2 <= B*k2
for t in T:
    model.addConstr(Qr2[t] <= B_const * k2[t])

# Qs <= B*k0, Qs再帰, x/y制約
for t in T:
    model.addConstr(Qs[t] <= B_const * k0[t])
    model.addConstr(x[t] <= B_const * a[t])
    model.addConstr(y[t] <= B_const * (1 - a[t]))

for t in T[:-1]:
    rhs = f * x[t] - y[t] / (f * f)
    model.addConstr(Qs[t + 1] == Qs[t] + rhs)

# ✅ 目的関数：∑ λt (x - y) - ∑ 8 * R[b] * ΔkW[b] - ∑ 6 * R2[b] * ΔkW2[b]
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
    for t in T:
        print(f"t={t:02d}, k0={k0[t].X:.3f}, k1={k1[t].X:.3f}, k2={k2[t].X:.3f}, Qr={Qr[t].X:.2f}, Qr2={Qr2[t].X:.2f}, Qs={Qs[t].X:.2f}")
    print("\nΔkW[b] の最適値:")
    for b in B:
        print(f"b={b}, ΔkW={delta_kW[b].X:.3f}, ΔkW2={delta_kW2[b].X:.3f}")
else:
    print("最適解が見つかりませんでした。")
