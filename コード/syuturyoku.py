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
print("\n変数 x[i,j] の値:")
for i in i2:
    for j in j2:
        print(f"x2[{i},{j}] = {x2[i, j].X:.4f}")

print("\n変数 y[i,j] の値:")
for i in i2:
    for j in j2:
        print(f"y2[{i},{j}] = {y2[i, j].X:.4f}")

else:
    print("最適解が見つかりませんでした。")