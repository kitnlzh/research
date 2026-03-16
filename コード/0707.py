import pandas as pd
from gurobipy import Model, GRB

# インデックス定義
i_set = range(4)
j_set = range(4)

# Excelから s, t シートを読み込み（4x4）
df_s = pd.read_excel(r"C:/Users/kit02/OneDrive/研究/エクセル/0704サイクル劣化.xlsx", sheet_name='s', header=None, nrows=4, usecols=range(4))
df_t = pd.read_excel(r"C:/Users/kit02/OneDrive/研究/エクセル/0704サイクル劣化.xlsx", sheet_name='t', header=None, nrows=4, usecols=range(4))

S_matrix = df_s.values.tolist()
T_matrix = df_t.values.tolist()

# パラメータ定義
B = 1000
f = 0.95

# モデル作成
model = Model("simple_model")

# 変数定義
x = model.addVars(i_set, j_set, lb=0, vtype=GRB.CONTINUOUS, name="x")
y = model.addVars(i_set, j_set, lb=0, vtype=GRB.CONTINUOUS, name="y")

Qs = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name="Qs")
Qr1 = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name="Qr1")
Qr2 = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name="Qr2")
Pt_sel = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name="Pt_sel")
delta_kWh = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name="delta_kWh")
delta_kWh2 = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name="delta_kWh2")

# 制約式の追加
model.addConstr(sum(x[i, j] for i in i_set for j in j_set) == (Qs + Qr1 + Qr2) / B, name="x_sum_constraint")
model.addConstr(sum(y[i, j] for i in i_set for j in j_set) == (Pt_sel + delta_kWh + delta_kWh2) / (B * f * f), name="y_sum_constraint")

# 目的関数
expr = sum(S_matrix[i][j] * x[i, j] + T_matrix[i][j] * y[i, j] for i in i_set for j in j_set)
model.setObjective(expr, GRB.MINIMIZE)

# 最適化
model.optimize()

# 出力
if model.status == GRB.OPTIMAL:
    print("最適値:", model.objVal)
    for i in i_set:
        for j in j_set:
            print(f"x[{i},{j}] = {x[i,j].X:.4f}, y[{i},{j}] = {y[i,j].X:.4f}")
else:
    print("最適解が見つかりませんでした。")
