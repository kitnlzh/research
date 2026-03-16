
import pandas as pd
from gurobipy import Model, GRB

# ExcelからλとRを読み込む
data_path = r"C:\Users\tam1015\Desktop\kitano\Data5.xlsx"
df = pd.read_excel(data_path, sheet_name=0)

lambda_t = df['spot6'].tolist()[:48]
R_b = df['pri6'].dropna().tolist()[:8]
R2_b = df['sec6'].dropna().tolist()[:8]
S = df['Si'].dropna().tolist()[:10]

# 定数
alpha = 0.5
f = 0.95
p = 1.0
p2 = 1.0
delta_t = 0.5
B_const = 40
D = 5 * B_const / 0.3
T = range(48)
T_q = range(49)
B = range(8)
I = range(10)

# モデル作成
model = Model("full_model")
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

# 目的関数（仮に定義）
expr = (
    sum(lambda_t[t] * (P_buy[t] - P_sel[t]) for t in T)
    - sum(6 * R_b[b] * delta_kW[b] for b in B)
    - sum(6 * R2_b[b] * delta_kW2[b] for b in B)
    + sum(D * x[t, i] * S[i] for t in T for i in I)
)
model.setObjective(expr, GRB.MINIMIZE)

# 最適化
model.optimize()

# 出力：S, x, S*x
if model.status == GRB.OPTIMAL:
    print("S[i], 合計 x[:, i], S[i]*合計x[:, i]")
    for i in I:
        total_xi = sum(x[t, i].X for t in T)
        print(f"i={i}, S={S[i]:.4f}, x_total={total_xi:.4f}, S*x={S[i]*total_xi:.4f}")
else:
    print("最適解が見つかりませんでした。")
