import pandas as pd

excel_path = r"C:/Users/kit02/OneDrive/研究/エクセル/0704サイクル劣化.xlsx"
sheet_names = pd.ExcelFile(excel_path).sheet_names
print(sheet_names)
