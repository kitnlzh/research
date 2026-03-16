import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# パラメータ設定
T = range(49)
B = range(8)
I = range(9)

# 乱数シード
np.random.seed(1)

# データ生成
delta_kW = [213.56, 391.1894, 752.0885, 1442.7157, 656.5941, 0.0, 298.8224, 135.9970]
delta_kW2 = [0.0] * 8
a = [0] * 49
P_buy = [0.0] * 49
P_sel = [0.0] * 49

# モデル構築
model = gp.Model("BatteryOptimization")

# 変数定義
Qr = model.addVars(T, lb=0.0, name="Qr")
Qr2 = model.addVars(T, lb=0.0, name="Qr2")
Qs = model.addVars(T, lb=0.0, name="Qs")
z = model.addVars(T, I, vtype=GRB.BINARY, name="z")

# 初期SOC
model.addConstr(Qr[0] == 949.2795)
model.addConstr(Qr2[0] == 0.0)
model.addConstr(Qs[0] == 0.0)

# 状態遷移
for t in T[:-1]:
    model.addConstr(Qr[t + 1] == Qr[t] - gp.quicksum(delta_kW[b] * z[t, b] for b in B))
    model.addConstr(Qr2[t + 1] == Qr2[t] - gp.quicksum(delta_kW2[b] * z[t, b] for b in B))
    model.addConstr(Qs[t + 1] == Qs[t] + gp.quicksum(delta_kW[b] * z[t, 8] for b in B))

# 各時刻で1つの状態だけ選択
for t in T:
    model.addConstr(gp.quicksum(z[t, i] for i in I) == 1)

# 目的関数（例: 最小化）
model.setObjective(Qs[48], GRB.MAXIMIZE)

# 最適化
model.optimize()

if model.status == GRB.OPTIMAL:
    print("\nSOC Qr, Qr2, Qs:")
    for t in T:
        print(f"t={t:02d}, Qr={Qr[t].X:.4f}, Qr2={Qr2[t].X:.4f}, Qs={Qs[t].X:.4f}")

    # グラフ描画
    Qr_vals = [Qr[t].X for t in T]
    Qr2_vals = [Qr2[t].X for t in T]
    Qs_vals = [Qs[t].X for t in T]

    plt.plot(T, Qr_vals, label='Qr')
    plt.plot(T, Qr2_vals, label='Qr2')
    plt.plot(T, Qs_vals, label='Qs')
    plt.xlabel('Time')
    plt.ylabel('SOC')
    plt.title('Battery SOC over Time')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("soc_plot.png")
    plt.close()

    # z[t, i]のExcel出力
    z_data = []
    for t in T:
        row = [int(z[t, i].X) for i in range(9)]  # i=0〜8
        z_data.append(row)

    df_z = pd.DataFrame(z_data, columns=[f"i={i}" for i in range(9)])
    output_path = os.path.join(os.path.expanduser("~"), "Desktop", "z_values.xlsx")
    df_z.to_excel(output_path, index_label="t")
    print(f"\nz[t, i]の値（i=0〜8）をExcelに出力しました: {output_path}")
