#!/usr/bin/env python3
"""Safe reader and editor for the company cash flow workbook (needs openpyxl).

File: --file, else $OPS_DESK_CASHFLOW_FILE, else "cashflow_file" in ~/.ops-desk.json (an Excel file in a OneDrive-synced folder).

Layout relied on (verified by `check`):
  sheet 'Cash Flow': opening date A3, opening balance D3, ledger from row 5 down to the
  'Closing balance' row, then the 'Lowest balance' row. Payments are positive, receipts
  negative (column D), Done flag in F (1 = already inside the opening balance), balance
  formulas in E chained row to row.
  sheet 'Month Summary': windows in H5:I10, formulas pointing at the ledger range.

Every change inserts or removes whole rows the way Excel does: it re-chains the balance
formulas, shifts recurring links (=D30), summary ranges, highlights and print area, checks
the result, backs up the old file, then replaces it atomically. Output is JSON.
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl
from copy import copy
from openpyxl.formatting.formatting import ConditionalFormattingList

import ops

SHEET = "Cash Flow"
SUMMARY = "Month Summary"
OPEN_ROW = 5
KEEP_BACKUPS = 20

REF = re.compile(
    r"(?<![\w.])((?:'[^']+'|[A-Za-z_][\w.]*)!)?(\$?[A-Z]{1,3})(\$?)(\d+)(?::(\$?[A-Z]{1,3})(\$?)(\d+))?"
)
D_LINK = re.compile(r"=\$?D\$?(\d+)")


class CashflowError(Exception):
    pass


# ---------- layout helpers ----------

def close_row(ws):
    for r in range(OPEN_ROW + 1, ws.max_row + 1):
        if str(ws.cell(r, 2).value or "").startswith("Closing balance"):
            return r
    raise CashflowError("no 'Closing balance' row found in the Cash Flow sheet")


def as_date(v):
    return v.date() if isinstance(v, datetime) else v


def amount(ws, r, seen=()):
    v = ws.cell(r, 4).value
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    m = D_LINK.fullmatch(str(v).strip())
    if m and int(m.group(1)) not in seen + (r,):
        return amount(ws, int(m.group(1)), seen + (r,))
    raise CashflowError(f"D{r}: cannot evaluate '{v}'")


def balances(ws):
    bal = {OPEN_ROW: float(ws["D3"].value)}
    for r in range(OPEN_ROW + 1, close_row(ws)):
        done = ws.cell(r, 6).value == 1
        bal[r] = bal[r - 1] - (0.0 if done else amount(ws, r))
    return bal


def key_figures(ws):
    bal = balances(ws)
    close = close_row(ws)
    low_row = min(bal, key=lambda r: bal[r])
    return {
        "opening_inr": bal[OPEN_ROW],
        "closing_inr": round(bal[close - 1], 2),
        "lowest_inr": round(bal[low_row], 2),
        "lowest_on": str(as_date(ws.cell(low_row, 1).value)),
    }


def months(wb, ws):
    bal = balances(ws)
    ms = wb[SUMMARY]
    rows = range(OPEN_ROW + 1, close_row(ws))
    opening, out, r = float(ws["D3"].value), [], 5
    while isinstance(ms.cell(r, 1).value, datetime):
        lo, hi = as_date(ms.cell(r, 8).value), as_date(ms.cell(r, 9).value)
        inside = [x for x in rows if lo <= as_date(ws.cell(x, 1).value) <= hi]
        receipts = -sum(amount(ws, x) for x in inside if amount(ws, x) < 0)
        payments = sum(amount(ws, x) for x in inside if amount(ws, x) > 0)
        closing = opening + receipts - payments
        lowest = min([opening] + [bal[x] for x in inside])
        out.append({
            "month": ms.cell(r, 1).value.strftime("%b %Y"), "from": str(lo), "to": str(hi),
            "opening_inr": round(opening, 2), "receipts_inr": round(receipts, 2),
            "payments_inr": round(payments, 2), "closing_inr": round(closing, 2),
            "lowest_inr": round(lowest, 2), "shortfall": lowest < 0,
        })
        opening, r = closing, r + 1
    return out


# ---------- integrity check ----------

def check_workbook(wb):
    errors, warnings = [], []
    if SHEET not in wb or SUMMARY not in wb:
        return [f"workbook needs sheets '{SHEET}' and '{SUMMARY}'"], warnings
    ws = wb[SHEET]
    try:
        close = close_row(ws)
    except CashflowError as e:
        return [str(e)], warnings
    if not isinstance(ws["D3"].value, (int, float)):
        errors.append("D3 (opening balance) must be a number")
    if not isinstance(ws["A3"].value, datetime):
        errors.append("A3 (opening date) must be a date")
    if any(rng.min_row >= OPEN_ROW for rng in ws.merged_cells.ranges):
        errors.append("merged cells inside the ledger are not supported")
    prev = None
    for r in range(OPEN_ROW + 1, close):
        d = ws.cell(r, 1).value
        if not isinstance(d, datetime):
            errors.append(f"A{r}: date missing or not a date")
        elif prev and d < prev:
            warnings.append(f"row {r} is out of date order")
        prev = d if isinstance(d, datetime) else prev
        flag = ws.cell(r, 6).value
        if flag not in (None, 0, 1):
            errors.append(f"F{r}: Done must be 1 or blank")
        expect = f"=E{r - 1}" if flag == 1 else f"=E{r - 1}-N(D{r})"
        if ws.cell(r, 5).value != expect:
            errors.append(f"E{r}: balance formula should be {expect}, found {ws.cell(r, 5).value}")
        try:
            amount(ws, r)
        except CashflowError as e:
            errors.append(str(e))
    if ws.cell(close, 5).value != f"=E{close - 1}":
        errors.append(f"E{close}: closing formula should be =E{close - 1}")
    low = str(ws.cell(close + 1, 5).value)
    if low != f"=MIN(E5:E{close - 1})":
        errors.append(f"E{close + 1}: lowest-balance formula should be =MIN(E5:E{close - 1})")
    text = " ".join(str(c.value) for row in wb[SUMMARY].iter_rows() for c in row if isinstance(c.value, str))
    for end in re.findall(r"'Cash Flow'!\$[A-F]\$5:\$[A-F]\$(\d+)", text):
        if int(end) != close - 1:
            errors.append(f"Month Summary range ends at row {end}, ledger ends at {close - 1}")
            break
    return errors, warnings


# ---------- Excel-style row shifting ----------

def shift_text(text, at, delta, own_sheet, extend, shrink=None):
    """Shift references to rows >= at by delta.

    extend: a range ending at at-1 grows to include the inserted row.
    shrink: a range ending on this (deleted) row ends one row earlier.
    """
    def repl(m):
        sheet = m.group(1)
        if (sheet.rstrip("!").strip("'") if sheet else own_sheet) != SHEET:
            return m.group(0)
        r1 = int(m.group(4))
        r1 = r1 + delta if r1 >= at else r1
        out = f"{sheet or ''}{m.group(2)}{m.group(3)}{r1}"
        if m.group(7):
            r2 = int(m.group(7))
            if shrink is not None and r2 == shrink and r1 < r2:
                r2 -= 1
            elif r2 >= at or (extend and r2 == at - 1):
                r2 += delta
            out += f":{m.group(5)}{m.group(6)}{r2}"
        return out
    parts = text.split('"')
    parts[::2] = [REF.sub(repl, p) for p in parts[::2]]
    return '"'.join(parts)


def shift_workbook(wb, at, delta, extend, shrink=None):
    ws = wb[SHEET]
    for sheet in wb:
        for row in sheet.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    c.value = shift_text(c.value, at, delta, sheet.title, extend, shrink)
    old = ws.conditional_formatting
    new = ConditionalFormattingList()
    for rng, rules in old._cf_rules.items():
        sqref = shift_text(str(rng.sqref), at, delta, SHEET, extend, shrink)
        for rule in rules:
            rule.formula = [shift_text(f, at, delta, SHEET, extend, shrink) for f in rule.formula]
            new.add(sqref, rule)
    ws.conditional_formatting = new
    if ws.print_area:
        area = shift_text(ws.print_area.split("!")[-1], at, delta, SHEET, extend, shrink)
        ws.print_area = area.replace("$", "")


def shift_heights(ws, at, delta):
    heights = {r: d.height for r, d in ws.row_dimensions.items() if d.height is not None}
    for r in heights:
        ws.row_dimensions[r].height = None
    for r, h in heights.items():
        ws.row_dimensions[r + delta if r >= at else r].height = h
    if delta > 0 and heights.get(at - 1):
        ws.row_dimensions[at].height = heights[at - 1]


def rechain(ws):
    close = close_row(ws)
    for r in range(OPEN_ROW + 1, close):
        ws.cell(r, 5).value = f"=E{r - 1}" if ws.cell(r, 6).value == 1 else f"=E{r - 1}-N(D{r})"
    ws.cell(close, 5).value = f"=E{close - 1}"
    ws.cell(close + 1, 5).value = f"=MIN(E5:E{close - 1})"
    ws.cell(close + 1, 7).value = (
        f'="on "&TEXT(INDEX(A5:A{close - 1},MATCH(MIN(E5:E{close - 1}),E5:E{close - 1},0)),"dd-mmm-yy")'
    )


def linked_from(ws, r):
    return [x for x in range(OPEN_ROW + 1, close_row(ws))
            if x != r and (m := D_LINK.fullmatch(str(ws.cell(x, 4).value or "").strip())) and int(m.group(1)) == r]


def insert_row(wb, ws, k):
    old_close = close_row(ws)
    ws.insert_rows(k)
    shift_workbook(wb, k, 1, extend=(k == old_close))
    shift_heights(ws, k, 1)


def delete_row(wb, ws, k):
    if linked_from(ws, k):
        raise CashflowError(f"row {k} is the base of recurring rows {linked_from(ws, k)}; change its amount instead")
    ws.delete_rows(k)
    shift_workbook(wb, k + 1, -1, extend=False, shrink=k)
    shift_heights(ws, k + 1, -1)


def position_for(ws, when, rank):
    for r in range(OPEN_ROW + 1, close_row(ws)):
        d = as_date(ws.cell(r, 1).value)
        r_rank = 1 if amount(ws, r) < 0 else 0
        if (d, r_rank) > (when, rank):
            return r
    return close_row(ws)


def style_template(ws, k):
    for r in range(k - 1, OPEN_ROW, -1):
        if isinstance(ws.cell(r, 4).value, (int, float)) and ws.cell(r, 6).value != 1:
            return r
    return OPEN_ROW + 1


def fill_row(ws, r, template, when, desc, head, amt, remark):
    for col in range(1, 8):
        ws.cell(r, col)._style = copy(ws.cell(template, col)._style)
    ws.cell(r, 1).value = datetime(when.year, when.month, when.day)
    ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 4).value = desc, head, amt
    ws.cell(r, 6).value, ws.cell(r, 7).value = None, remark


# ---------- file handling ----------

def resolve_path(arg):
    p = arg or os.environ.get("OPS_DESK_CASHFLOW_FILE") or ops.settings().get("cashflow_file")
    if not p:
        raise CashflowError("no workbook: pass --file, set OPS_DESK_CASHFLOW_FILE, or run the setup skill")
    path = Path(p).expanduser()
    if not path.exists():
        raise CashflowError(f"file not found: {path}")
    return path


def open_in_excel(path):
    # Excel names the lock file "~$" + file name with its first two characters replaced
    return any(p.name[2:] in path.name for p in path.parent.glob("~$*"))


def backup_dir():
    return ops.data_dir() / "backups"


def save(wb, path):
    if open_in_excel(path):
        raise CashflowError("the workbook is open in Excel (lock file found); close it or retry in a minute")
    bdir = backup_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = bdir / f"{path.stem}.{stamp}{path.suffix}"
    shutil.copy2(path, bak)
    for old in sorted(bdir.glob(f"{path.stem}.*{path.suffix}"))[:-KEEP_BACKUPS]:
        old.unlink()
    tmp = path.with_name(f".ops-desk-tmp-{os.getpid()}{path.suffix}")
    wb.save(tmp)
    os.replace(tmp, path)
    return str(bak)


def row_view(ws, r):
    d = amount(ws, r)
    return {
        "row": r, "date": str(as_date(ws.cell(r, 1).value)), "desc": ws.cell(r, 2).value,
        "head": ws.cell(r, 3).value, "amount_inr": abs(d), "kind": "receipt" if d < 0 else "payment",
        "done": ws.cell(r, 6).value == 1, "remark": ws.cell(r, 7).value,
    }


def parse_items(ws, items):
    rows = []
    for item in items or []:
        num, _, expect = item.partition("=")
        if not num.isdigit() or not expect:
            raise CashflowError(f"--item must look like ROW=TEXT (got '{item}')")
        r = int(num)
        if not OPEN_ROW < r < close_row(ws):
            raise CashflowError(f"row {r} is not a ledger row")
        if expect.lower() not in str(ws.cell(r, 2).value or "").lower():
            raise CashflowError(f"row {r} is '{ws.cell(r, 2).value}', not '{expect}'. List again; row numbers move after edits")
        rows.append(r)
    if not rows:
        raise CashflowError("give at least one --item ROW=TEXT")
    return rows


# ---------- commands ----------

def cmd_list(ws, a):
    lo = date.fromisoformat(a.date_from) if a.date_from else date.min
    hi = date.fromisoformat(a.date_to) if a.date_to else date.max
    bal = balances(ws)
    out = []
    for r in range(OPEN_ROW + 1, close_row(ws)):
        v = row_view(ws, r)
        if not lo <= as_date(ws.cell(r, 1).value) <= hi:
            continue
        if a.head and (v["head"] or "").lower() != a.head.lower():
            continue
        if a.pending and v["done"]:
            continue
        out.append({**v, "balance_inr": round(bal[r], 2)})
    return out


def cmd_summary(wb, ws, a):
    heads = {}
    for r in range(OPEN_ROW + 1, close_row(ws)):
        if ws.cell(r, 6).value == 1:
            continue
        h = ws.cell(r, 3).value or "(none)"
        d = amount(ws, r)
        e = heads.setdefault(h, {"payments_inr": 0.0, "receipts_inr": 0.0})
        e["receipts_inr" if d < 0 else "payments_inr"] += abs(d)
    return {
        **key_figures(ws), "opening_date": str(as_date(ws["A3"].value)),
        "months": months(wb, ws), "pending_by_head": {k: {m: round(x, 2) for m, x in v.items()} for k, v in sorted(heads.items())},
    }


def mutate(wb, ws, a, fn):
    before = key_figures(ws)
    changed = fn()
    rechain(ws)
    errors, _ = check_workbook(wb)
    if errors:
        raise CashflowError("result failed integrity check, nothing saved: " + "; ".join(errors))
    result = {"ok": True, "before": before, "after": key_figures(ws), "rows": changed, "saved": False}
    if not a.dry_run:
        result["backup"] = save(wb, resolve_path(a.file))
        result["saved"] = True
    return result


def cmd_add(wb, ws, a):
    when = date.fromisoformat(a.date)
    if a.amount <= 0:
        raise CashflowError("--amount must be positive; use --kind receipt for money in")
    heads = {str(ws.cell(r, 3).value) for r in range(OPEN_ROW + 1, close_row(ws)) if ws.cell(r, 3).value}
    if a.head not in heads and not a.allow_new_head:
        raise CashflowError(f"unknown head '{a.head}'. Known: {sorted(heads)}. Use --allow-new-head to add a new one")
    signed = -a.amount if a.kind == "receipt" else a.amount
    norm = lambda s: re.sub(r"\W+", " ", str(s)).strip().lower()
    for r in range(OPEN_ROW + 1, close_row(ws)):
        if (as_date(ws.cell(r, 1).value) == when and amount(ws, r) == signed
                and norm(ws.cell(r, 2).value) == norm(a.desc)) and not a.force:
            raise CashflowError(f"row {r} already has this item (same date, amount, description). Use --force to add anyway")

    def do():
        k = position_for(ws, when, 1 if a.kind == "receipt" else 0)
        template = style_template(ws, k)
        insert_row(wb, ws, k)
        t = template if template < k else template + 1
        fill_row(ws, k, t, when, a.desc, a.head, signed, a.remark)
        return [k]
    result = mutate(wb, ws, a, do)
    result["rows"] = [row_view(ws, r) for r in result["rows"]]
    return result


def cmd_remove(wb, ws, a):
    rows = parse_items(ws, a.item)
    views = [row_view(ws, r) for r in rows]

    def do():
        for r in sorted(rows, reverse=True):
            delete_row(wb, ws, r)
        return []
    result = mutate(wb, ws, a, do)
    result["removed"] = views
    return result


def cmd_amount(wb, ws, a):
    (r,) = parse_items(ws, a.item)
    if a.new_amount <= 0:
        raise CashflowError("--amount must be positive")
    if D_LINK.fullmatch(str(ws.cell(r, 4).value or "").strip()) and not a.unlink:
        raise CashflowError(f"row {r} follows another row's amount; change that base row, or pass --unlink")
    followers = linked_from(ws, r)
    sign = -1 if amount(ws, r) < 0 else 1

    def do():
        ws.cell(r, 4).value = sign * a.new_amount
        return [r]
    result = mutate(wb, ws, a, do)
    result["rows"] = [row_view(ws, x) for x in result["rows"]]
    result["rows_following_this_amount"] = followers
    return result


def cmd_move(wb, ws, a):
    (r,) = parse_items(ws, a.item)
    when = date.fromisoformat(a.date)
    prev_d = as_date(ws["A3"].value) if r - 1 == OPEN_ROW else as_date(ws.cell(r - 1, 1).value)
    next_d = as_date(ws.cell(r + 1, 1).value)
    if not (prev_d <= when <= next_d):
        raise CashflowError(
            "new date falls outside this row's position in the date order; "
            "remove and re-add the item (rows that other rows link to cannot be moved automatically)"
        )

    def do():
        ws.cell(r, 1).value = datetime(when.year, when.month, when.day)
        return [r]
    result = mutate(wb, ws, a, do)
    result["rows"] = [row_view(ws, x) for x in result["rows"]]
    return result


def cmd_mark_done(wb, ws, a):
    rows = parse_items(ws, a.item)
    as_of = date.fromisoformat(a.as_of)
    late = [r for r in rows if as_date(ws.cell(r, 1).value) > as_of]
    if late:
        raise CashflowError(f"rows {late} are dated after --as-of; change their date to the payment date first")
    old_open_date = as_date(ws["A3"].value)

    def do():
        for r in rows:
            ws.cell(r, 6).value = 1
            note = f"Done on {as_of:%d.%m.%Y}: already in opening balance, not deducted again"
            ws.cell(r, 7).value = f"{ws.cell(r, 7).value}; {note}" if ws.cell(r, 7).value else note
        ws["D3"].value = a.opening_balance
        ws["A3"].value = datetime(as_of.year, as_of.month, as_of.day)
        ms = wb[SUMMARY]
        if as_date(ms["H5"].value) == old_open_date:
            ms["H5"].value = datetime(as_of.year, as_of.month, as_of.day)
        return rows
    result = mutate(wb, ws, a, do)
    result["rows"] = [row_view(ws, x) for x in result["rows"]]
    result["note"] = "Opening balance and date were set from the figures you gave. They are the bank truth."
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="workbook path (default $OPS_DESK_CASHFLOW_FILE)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("summary")
    ls = sub.add_parser("list")
    ls.add_argument("--from", dest="date_from")
    ls.add_argument("--to", dest="date_to")
    ls.add_argument("--head")
    ls.add_argument("--pending", action="store_true")
    p = {}
    for name in ("add", "remove", "amount", "move", "mark-done"):
        p[name] = sub.add_parser(name)
        p[name].add_argument("--dry-run", action="store_true", help="validate and show the effect, do not save")
    ad = p["add"]
    ad.add_argument("--date", required=True)
    ad.add_argument("--desc", required=True)
    ad.add_argument("--head", required=True)
    ad.add_argument("--amount", type=float, required=True)
    ad.add_argument("--kind", choices=["payment", "receipt"], required=True)
    ad.add_argument("--remark", default="")
    ad.add_argument("--allow-new-head", action="store_true")
    ad.add_argument("--force", action="store_true")
    for name in ("remove", "amount", "move", "mark-done"):
        p[name].add_argument("--item", action="append", help="ROW=TEXT; TEXT must appear in the row's description")
    p["amount"].add_argument("--amount", dest="new_amount", type=float, required=True)
    p["amount"].add_argument("--unlink", action="store_true")
    p["move"].add_argument("--date", required=True)
    p["mark-done"].add_argument("--opening-balance", type=float, required=True)
    p["mark-done"].add_argument("--as-of", required=True)
    a = ap.parse_args(argv)

    try:
        path = resolve_path(a.file)
        wb = openpyxl.load_workbook(path)
        errors, warnings = check_workbook(wb)
        if a.cmd == "check":
            out = {"ok": not errors, "errors": errors, "warnings": warnings}
        elif errors:
            out = {"ok": False, "errors": errors}
        else:
            ws = wb[SHEET]
            out = {
                "list": lambda: cmd_list(ws, a), "summary": lambda: cmd_summary(wb, ws, a),
                "add": lambda: cmd_add(wb, ws, a), "remove": lambda: cmd_remove(wb, ws, a),
                "amount": lambda: cmd_amount(wb, ws, a), "move": lambda: cmd_move(wb, ws, a),
                "mark-done": lambda: cmd_mark_done(wb, ws, a),
            }[a.cmd]()
    except (CashflowError, ValueError) as e:
        out = {"ok": False, "errors": [str(e)]}
    print(json.dumps(out, indent=2, default=str))
    return 0 if not isinstance(out, dict) or out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
