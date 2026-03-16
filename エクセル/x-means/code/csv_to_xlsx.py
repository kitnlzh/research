from pathlib import Path
import pandas as pd
import csv

csv_dir = Path(r"C:\Users\kit02\OneDrive\研究\エクセル\新しいフォルダー")
out_xlsx = Path(r"C:\Users\kit02\OneDrive\研究\エクセル\xlsx\output.xlsx")

ENCODINGS = ["cp932", "utf-8-sig", "utf-8"]

def read_csv_flexible(p: Path) -> pd.DataFrame:
    last_err = None
    for enc in ENCODINGS:
        try:
            rows = []
            with open(p, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f, delimiter=",", quotechar='"')
                for r in reader:
                    rows.append(r)

            if not rows:
                return pd.DataFrame()

            maxlen = max(len(r) for r in rows)
            padded = [r + [""] * (maxlen - len(r)) for r in rows]
            cols = [f"col{i+1}" for i in range(maxlen)]
            return pd.DataFrame(padded, columns=cols)

        except Exception as e:
            last_err = e

    raise last_err

csv_files = sorted(csv_dir.glob("*.csv"))
if not csv_files:
    raise FileNotFoundError(f"No CSV files found in: {csv_dir}")

with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
    for f in csv_files:
        print(f"Reading: {f.name}")
        df = read_csv_flexible(f)

        sheet = f.stem
        for ch in r'[]:*?/\\':
            sheet = sheet.replace(ch, "_")
        sheet = sheet[:31] if sheet else "sheet"

        df.to_excel(writer, sheet_name=sheet, index=False)

print(f"Saved: {out_xlsx}")