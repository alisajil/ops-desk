"""Build a fictional workbook with the same structure as the real cash flow file.

Usage: python3 tests/make_example.py examples/cashflow-example.xlsx
"""
import sys
from datetime import datetime

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill

BLUE = Font(color="FF0000FF")
BOLD = Font(bold=True)
DATE_FMT = "d\\-mmm\\-yy"
MONEY_FMT = "#,##0.00;\\-#,##0.00"

# date, description, head, amount (payments +, receipts -), done flag, remark
LEDGER = [
    (datetime(2026, 10, 15), "Vendor X balance payment", "Vendor", 50000, 1, "Done: already in opening balance"),
    (datetime(2026, 10, 22), "Client A invoice 1", "Receipt", -300000, 1, "Received: already in opening balance"),
    (datetime(2026, 10, 26), "Project Alpha fittings", "Project Alpha", 100000, None, None),
    (datetime(2026, 10, 26), "Client A advance", "Receipt", -200000, None, None),
    (datetime(2026, 11, 5), "Salary Sep", "Monthly", 400000, None, None),
    (datetime(2026, 12, 5), "Salary Oct", "Monthly", "=D10", None, None),
    (datetime(2027, 1, 5), "Salary Nov", "Monthly", "=D10", None, None),
    (datetime(2027, 3, 31), "Software licence", "Software", 90000, None, None),
]
FIRST = 6


def build(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cash Flow"
    last = FIRST + len(LEDGER) - 1
    close, low = last + 1, last + 2
    ws["A1"], ws["A2"] = "EXAMPLE COMPANY PRIVATE LIMITED", "Budget: Cash Flow (fictional)"
    ws.merge_cells("A1:G1")
    ws.merge_cells("A2:G2")
    ws["A3"], ws["B3"], ws["D3"] = datetime(2026, 10, 24), "Fund Available -", 1350000
    for col, name in zip("ABCDEFG", ["Due Date", "Payments \\ (Receipts)", "Head", "IN Rupees", "Balance", "Done (1/0)", "Remarks if any"]):
        ws[f"{col}4"] = name
    ws["A5"], ws["B5"], ws["E5"], ws["F5"] = "=A3", "Opening bank balance (fund available)", "=D3", 1
    for i, (when, desc, head, amt, done, remark) in enumerate(LEDGER):
        r = FIRST + i
        ws[f"A{r}"], ws[f"B{r}"], ws[f"C{r}"], ws[f"D{r}"] = when, desc, head, amt
        ws[f"E{r}"] = f"=E{r - 1}" if done else f"=E{r - 1}-N(D{r})"
        ws[f"F{r}"], ws[f"G{r}"] = done, remark
        ws[f"A{r}"].number_format = DATE_FMT
        ws[f"D{r}"].number_format = MONEY_FMT
        if isinstance(amt, (int, float)):
            ws[f"D{r}"].font = BLUE
    ws[f"A{close}"], ws[f"B{close}"], ws[f"E{close}"] = datetime(2027, 3, 31), "Closing balance at end of cash flow period", f"=E{last}"
    ws[f"B{low}"], ws[f"E{low}"] = "Lowest balance in the period", f"=MIN(E5:E{last})"
    ws[f"G{low}"] = f'="on "&TEXT(INDEX(A5:A{last},MATCH(MIN(E5:E{last}),E5:E{last},0)),"dd-mmm-yy")'
    for r in (close, low):
        ws[f"B{r}"].font = BOLD
    for r in range(1, low + 1):
        ws.row_dimensions[r].height = 18
    ws.freeze_panes = "A5"
    ws.conditional_formatting.add(f"F{FIRST}:F{last}", FormulaRule(formula=[f"ISBLANK(F{FIRST})"], fill=PatternFill(bgColor="FFFFFF99")))
    ws.conditional_formatting.add(f"A{FIRST}:C{last}", FormulaRule(formula=[f"$F{FIRST}=1"], fill=PatternFill(bgColor="FFE6D9F2")))
    ws.conditional_formatting.add(f"E5:E{last}", FormulaRule(formula=[f"E5=MIN($E$5:$E${last})"], fill=PatternFill(bgColor="FFFFFF00")))
    ws.print_area = f"A1:G{low}"

    ms = wb.create_sheet("Month Summary")
    ms["A1"] = "EXAMPLE COMPANY: month-wise summary"
    for col, name in zip("ABCDEFG", ["Month", "Opening balance", "Receipts (in)", "Payments (out)", "Closing balance", "Lowest balance in month", "Check"]):
        ms[f"{col}4"] = name
    windows = [
        (datetime(2026, 10, 1), datetime(2026, 10, 24), datetime(2026, 10, 31)),
        (datetime(2026, 11, 1), datetime(2026, 11, 1), datetime(2026, 11, 30)),
        (datetime(2026, 12, 1), datetime(2026, 12, 1), datetime(2026, 12, 31)),
        (datetime(2027, 1, 1), datetime(2027, 1, 1), datetime(2027, 1, 31)),
        (datetime(2027, 2, 1), datetime(2027, 2, 1), datetime(2027, 2, 28)),
        (datetime(2027, 3, 1), datetime(2027, 3, 1), datetime(2027, 3, 31)),
    ]
    cf = "'Cash Flow'!"
    rng = lambda c: f"{cf}${c}$5:${c}${last}"
    for i, (month, lo, hi) in enumerate(windows):
        r = 5 + i
        ms[f"A{r}"], ms[f"H{r}"], ms[f"I{r}"] = month, lo, hi
        ms[f"B{r}"] = f"={cf}D3" if i == 0 else f"=E{r - 1}"
        win = f'{rng("A")},">="&H{r},{rng("A")},"<="&I{r}'
        ms[f"C{r}"] = f'=-SUMIFS({rng("D")},{win},{rng("D")},"<0")'
        ms[f"D{r}"] = f'=SUMIFS({rng("D")},{win},{rng("D")},">0")'
        ms[f"E{r}"] = f"=B{r}+C{r}-D{r}"
        ms[f"F{r}"] = f'=MIN(B{r},_xlfn.MINIFS({rng("E")},{win}))'
        ms[f"G{r}"] = f'=IF(F{r}<0,"Shortfall","")'
    ms["A11"], ms["C11"], ms["D11"], ms["E11"] = "TOTAL", "=SUM(C5:C10)", "=SUM(D5:D10)", "=E10"
    ms["G11"] = f'=IF(ROUND(E11-{cf}E{close},2)=0,"OK","Mismatch")'
    wb.save(path)


if __name__ == "__main__":
    build(sys.argv[1])
