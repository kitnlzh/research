from pathlib import Path
import pandas as pd

# ===== ここを変更 =====
in_xlsx  = Path(r"C:\Users\kit02\OneDrive\研究\エクセル\SOC.xlsx")
out_xlsx = Path(r"C:\Users\kit02\OneDrive\研究\エクセル\新しいフォルダー\extracted_A_L_all_sheets.xlsx")
# =====================

# Excel列 → 0始まりindex
COL_A = 0   # A列（日付など）
COL_B = 1   # B列
COL_C = 2   # C列
COL_L = 11  # L列

cond_B = "システム約定結果"
cond_C = "平均落札価格（TSO別）[円/kW・30分]"

# 全シート名取得
xls = pd.ExcelFile(in_xlsx)
all_rows = []

for sh in xls.sheet_names:
    df = pd.read_excel(in_xlsx, sheet_name=sh, header=None)

    # 先頭行が "col1 col2 ..." みたいなダミーヘッダなら落とす
    if df.shape[0] > 0 and str(df.iat[0, 0]).strip().lower() == "col1":
        df = df.iloc[1:].reset_index(drop=True)

    # 列数不足のシートはスキップ
    if df.shape[1] <= max(COL_A, COL_B, COL_C, COL_L):
        continue

    b = df.iloc[:, COL_B].astype(str).str.strip()
    c = df.iloc[:, COL_C].astype(str).str.strip()
    mask = (b == cond_B) & (c == cond_C)

    if mask.any():
        picked = pd.DataFrame({
            "sheet": sh,
            "row_in_sheet": df.index[mask] + 1,  # Excelっぽい行番号（任意）
            "A_date": df.loc[mask].iloc[:, COL_A],
            "L_value": df.loc[mask].iloc[:, COL_L],
        })

        all_rows.append(picked)

# まとめて出力
out_df = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame(
    columns=["sheet", "row_in_sheet", "A_date", "L_value"]
)

out_df.to_excel(out_xlsx, index=False)
print(f"Saved: {out_xlsx}  (total matches: {len(out_df)})")