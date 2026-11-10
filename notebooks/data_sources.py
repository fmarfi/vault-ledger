"""Loaders that turn the downloaded public datasets into one common table.

Every source becomes rows of:
    source, group, vendor, description, amount, label_raw, account, kind, origin, language, licence

- label_raw: the dataset's own category, untouched
- account:   label_raw mapped onto Vault Ledger's 7 expense accounts by
             map_to_account(), or "EXCLUDE" (not an expense: sales, transfers,
             payroll, tax payments...) or "UNMAPPED" (no rule matched)
- kind:      "business" (company / public-body spending) or "personal"
- origin:    "real" or "synthetic"

Used by data_landscape.ipynb. Nothing here runs code from the downloads; it
only reads csv / xlsx / parquet files.
"""

from __future__ import annotations

import ast
import glob
import re
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
EXT = REPO / "data" / "external"
SYNTH = REPO / "data" / "synthetic" / "generated"

ACCOUNTS = [
    "Office Supplies Expense",
    "Software & Subscriptions Expense",
    "Utilities Expense",
    "Rent Expense",
    "Travel & Transport Expense",
    "Professional Services Expense",
    "General/Other Expense",
]
SHORT = {
    "Office Supplies Expense": "Office",
    "Software & Subscriptions Expense": "Software",
    "Utilities Expense": "Utilities",
    "Rent Expense": "Rent",
    "Travel & Transport Expense": "Travel",
    "Professional Services Expense": "Professional",
    "General/Other Expense": "General",
}


# ---------------------------------------------------------------------------
# Label mapping: dataset category text -> one of our accounts
# First matching rule wins, so the order matters.
# ---------------------------------------------------------------------------
_RULES: list[tuple[str, str]] = [
    ("EXCLUDE", r"revenue|\bsales\b|gross receipts|income|receipts|refund|returns and allowances|transfer|"
                r"owner|drawing|funds introduced|director.?s.? loan|\bloans?\b|payroll|wage|salar|pension|"
                r"sales tax payment|\bvat\b|credit card payment|interest|dividend|saving|grant|benefit|"
                r"care payments|social services clients|depreciation|capital|fixed asset|needs review|"
                r"ask the client|excluded|investment|\batm\b|cash withdrawal|stock comp|accrued|"
                r"personele exploitatie|externe inhuur|personeel"),
    ("General/Other Expense", r"bank|merchant fee|taxes and licen|insurance|verzeker"),
    ("Software & Subscriptions Expense", r"software|subscription|saas|\bict\b|\bit\b|information and comm|"
                r"information communication|computer|domain|website|hosting|\bapps?\b|cloud|digital|"
                r"internet services"),
    ("Utilities Expense", r"utilit|energy|electric|\bgas\b|water|telecom|telephone|phone|internet|broadband|"
                r"mobile|communications|energie|nutsvoorz"),
    ("Travel & Transport Expense", r"travel|transport|vehicle|\bcar\b|car allowance|motor|fuel|petrol|parking|"
                r"taxi|\brail|train\b|airline|air travel|flight|hotel|accommodation|lodging|subsistence|"
                r"mileage|vervoer|verblijf|\breis|automotive|contract hire|toll|bus lines|commuter"),
    ("Rent Expense", r"\brent|lease|leasing|\brates\b|huisvesting|office space|coworking|real estate"),
    ("Office Supplies Expense", r"office|stationery|printing|\bprint|supplies|furniture|furnishing|equipment|"
                r"materials|papier|benodigdheden|hardware|electronics|kantoor"),
    ("Professional Services Expense", r"professional|legal|consult|accountan|audit|advis|advies|solicitor|"
                r"notar|lawyer|attorney|subcontract|contractor|uitbesteden|interpret|translation|"
                r"recruitment|temporary|contract labo|fees and charges|professional fees"),
    ("General/Other Expense", r"meal|catering|food|restaurant|bars?\b|cafe|advertis|marketing|publicity|"
                r"promotion|training|education|opleiding|membership|dues|contribution|postage|shipping|"
                r"courier|\bmail|freight|repair|maintenance|cleaning|schoonmaak|clothing|uniform|misc|"
                r"general|other|overig|entertain|gift|grocer|supermarket|hospitality|representatie|leisure|"
                r"books|periodical|conference|seminar|events?\b|retail|wholesale|department store|"
                r"expenses?\b|services|diensten|cost of goods|materials"),
]
_COMPILED = [(acc, re.compile(p, re.I)) for acc, p in _RULES]


def map_to_account(label) -> str:
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return "UNMAPPED"
    text = str(label).strip()
    if not text:
        return "UNMAPPED"
    if text in ACCOUNTS:  # already our label
        return text
    for account, rx in _COMPILED:
        if rx.search(text):
            return account
    return "UNMAPPED"


# ---------------------------------------------------------------------------
# Reading helpers
# ---------------------------------------------------------------------------
def read_any(path, nrows=None) -> pd.DataFrame:
    path = str(path)
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
        return df.head(nrows) if nrows else df
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path, nrows=nrows)
    if path.endswith(".jsonl"):
        return pd.read_json(path, lines=True, nrows=nrows)
    for enc in ("utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, nrows=nrows, low_memory=False, on_bad_lines="skip")
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError:
            return pd.read_csv(path, encoding=enc, nrows=nrows, sep=None, engine="python", on_bad_lines="skip")
    return pd.DataFrame()


def files(pattern: str) -> list[str]:
    out = sorted(glob.glob(str(EXT / pattern), recursive=True))
    return [f for f in out if "/._" not in f.replace("\\", "/") and ".cache" not in f]


def pick(df: pd.DataFrame, *candidates: str):
    """First column whose name matches one of the candidates (case/space-insensitive)."""
    norm = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in df.columns}
    for cand in candidates:
        key = re.sub(r"[^a-z0-9]", "", cand.lower())
        if key in norm:
            return df[norm[key]]
    for cand in candidates:  # then a contains-match
        key = re.sub(r"[^a-z0-9]", "", cand.lower())
        for k, c in norm.items():
            if key and key in k:
                return df[c]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(r"[£$€,\s]", "", regex=True), errors="coerce")


def frame(source, vendor=None, description=None, amount=None, label=None, n=None) -> pd.DataFrame:
    n = n if n is not None else len(next(x for x in (vendor, description, label) if x is not None))
    blank = pd.Series([None] * n, dtype=object)

    def col(x):
        return blank if x is None else pd.Series(x).reset_index(drop=True)

    return pd.DataFrame({
        "source": source,
        "vendor": col(vendor).astype("string").str.strip(),
        "description": col(description).astype("string").str.strip(),
        "amount": _num(col(amount)) if amount is not None else pd.NA,
        "label_raw": col(label).astype("string").str.strip(),
    })


def stack(paths, fn, cap=None) -> pd.DataFrame:
    parts, total = [], 0
    for p in paths:
        try:
            df = read_any(p)
        except Exception:
            continue
        if df.empty:
            continue
        parts.append(fn(df))
        total += len(df)
        if cap and total >= cap:
            break
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# ---------------------------------------------------------------------------
# Source loaders. Each returns a frame() table.
# ---------------------------------------------------------------------------
def _synthetic():
    df = pd.read_csv(SYNTH / "transactions_2026.csv")
    meta = pd.read_csv(SYNTH / "metadata_2026.csv")
    out = frame("vault_synthetic_2026", df.vendor, df.description, df.amount, df.account)
    out["split"] = meta["split"].values
    out["language"] = meta["language"].values
    return out


def _pcard(folder, vendor_cols, label_cols, desc_cols=(), cap=None):
    def fn(df):
        return frame(folder, pick(df, *vendor_cols), pick(df, *desc_cols) if desc_cols else None,
                     pick(df, "net amount", "amount", "transaction amount", "net amount (£)"),
                     pick(df, *label_cols))
    return stack(files(f"transactions/{folder}/*.csv") + files(f"transactions/{folder}/*.xlsx"), fn, cap)


def _zerabooks():
    b = EXT / "transactions/gh_transaction-categorization-benchmark/data"
    t = read_any(b / "transactions.csv").merge(read_any(b / "labels.csv"), on="txn_id")
    coa = read_any(b / "chart-of-accounts.csv").rename(columns={"name": "coa_name"})
    t = t.merge(coa[["account", "coa_name"]], on="account", how="left")
    return frame("zerabooks_benchmark", None, t.description, t.amount, t.coa_name, n=len(t))


def _bookbench():
    parts = []
    for f in files("huggingface/rajo0113__bookbench/data/bank_line/*.parquet"):
        df = read_any(f)
        narr = df.bank_line.map(lambda x: (x if isinstance(x, dict) else ast.literal_eval(str(x))).get("narrative"))
        parts.append(frame("bookbench_uk_us", None, narr, df.amount, df.label_name, n=len(df)))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _swiss():
    f = files("huggingface/ChadSaglam__swiss-sme-bookkeeping-dataset/swiss_sme_bookkeeping_synthetic.csv")
    df = read_any(f[0])
    return frame("swiss_sme", None, df.text, df.amount_chf, df.account_name, n=len(df))


def _nl_rijksoverheid():
    """Wide table: one row per (ministry, supplier), one column per spend category
    holding a count. Melted to one row per supplier x category."""
    parts = []
    for f in files("ledger_standards/nl_rijksoverheid_inkoopdata/*/Totaal_OD_-_Totaal.xlsx"):
        df = read_any(f)
        cats = [c for c in df.columns if re.match(r"^\d{4} - ", str(c))]
        long = df.melt(id_vars=["Leveranciersnaam"], value_vars=cats, var_name="cat", value_name="n").dropna()
        long["cat"] = long["cat"].str.replace(r"^\d{4} - ", "", regex=True)
        parts.append(frame("nl_rijksoverheid_inkoop", long.Leveranciersnaam, None, None, long.cat, n=len(long)))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _leeds():
    def fn(df):
        return frame("uk_leeds_spend", pick(df, "Beneficiary Name", "Supplier Name"), None,
                     pick(df, "Amount"), pick(df, "Purpose"))
    out = stack(files("ledger_standards/uk_leeds_spend/*.csv"), fn)
    return out[out.vendor.fillna("").str.upper() != "REDACTED PERSONAL DATA"]


def _vynfi(cap=150_000):
    coa = read_any(files("huggingface/VynFi__vynfi-journal-entries-1m/chart_of_accounts.parquet")[0])
    names = dict(zip(coa.account_number.astype(str), coa.short_description))
    df = read_any(files("huggingface/VynFi__vynfi-journal-entries-1m/data/*.parquet")[0])
    df = df[df.line_text.notna() & (df.debit_amount > 0)].head(cap)
    return frame("vynfi_journal_1m", None, df.line_text, df.debit_amount,
                 df.gl_account.astype(str).map(names), n=len(df))


def _simple(source, pattern, vendor=None, desc=None, label=None, amount=None, cap=None):
    def load():
        def fn(df):
            return frame(source, pick(df, *vendor) if vendor else None, pick(df, *desc) if desc else None,
                         pick(df, *amount) if amount else None, pick(df, *label) if label else None, n=len(df))
        return stack(files(pattern), fn, cap)
    return load


def _filiptrocin():
    d = "transactions/gh_Bank_Transactions_classifier/data/"
    f = read_any(EXT / d / "bank_transaction_features.csv").merge(
        read_any(EXT / d / "bank_transaction_labels.csv"), on="bank_transaction_id")
    return frame("uk_bank_business_5class", None, f.bank_transaction_description,
                 f.bank_transaction_amount, f.bank_transaction_category, n=len(f))


# name -> (loader, group, kind, origin, language, licence)
SOURCES = {
    "vault_synthetic_2026": (_synthetic, "ours", "business", "synthetic", "nl/en", "ours"),
    "zerabooks_benchmark": (_zerabooks, "transactions", "business", "synthetic", "en", "MIT"),
    "bookbench_uk_us": (_bookbench, "huggingface", "business", "synthetic", "en", "see MANIFEST"),
    "swiss_sme": (_swiss, "huggingface", "business", "synthetic", "de/fr/it/en", "see MANIFEST"),
    "nl_rijksoverheid_inkoop": (_nl_rijksoverheid, "ledger_standards", "business", "real", "nl", "see MANIFEST"),
    "uk_calderdale_pcard": (lambda: _pcard("ukgov_calderdale_pcard_2024", ["Supplier Name"], ["Expense Type"]),
                            "transactions", "business", "real", "en", "OGL v3"),
    "uk_wakefield_pcard": (lambda: _pcard("ukgov_wakefield_pcard", ["Supplier Name", "Merchant Name"],
                                          ["Merchant Category"], cap=120_000),
                           "transactions", "business", "real", "en", "OGL v3"),
    "uk_stockport_pcard": (lambda: _pcard("ukgov_stockport_pcard", ["Supplier (Beneficiary)", "Supplier"],
                                          ["Purpose of Expenditure"]),
                           "transactions", "business", "real", "en", "OGL v3"),
    "uk_rushmoor_pcard": (lambda: _pcard("ukgov_rushmoor_pcard", ["Supplier Name"], ["Procurement Classification"],
                                         ["Purpose of Spend"]),
                          "transactions", "business", "real", "en", "OGL v3"),
    "uk_eden_pcard": (lambda: _pcard("ukgov_eden_pcard", ["Merchant Name"], ["MCC Description"]),
                      "transactions", "business", "real", "en", "OGL v3"),
    "uk_hmrc_gpc": (lambda: _pcard("ukgov_hmrc_gpc", ["Supplier"], ["__none__"], ["Description"]),
                    "transactions", "business", "real", "en", "OGL v3"),
    "uk_dwp_gpc": (lambda: _pcard("ukgov_dwp_gpc", ["Supplier", "Merchant Name"], ["__none__"], ["Comments", "Description"]),
                   "transactions", "business", "real", "en", "OGL v3"),
    "uk_leeds_spend": (_leeds, "ledger_standards", "business", "real", "en", "OGL v3"),
    "us_oklahoma_pcard": (_simple("us_oklahoma_pcard", "kaggle/oklahoma_pcard/*.csv", vendor=["Vendor"],
                                  desc=["Description"], label=["Merchant Category Code (MCC)"], amount=["Amount"],
                                  cap=150_000), "kaggle", "business", "real", "en", "see MANIFEST"),
    "uk_fsa_gpc": (_simple("uk_fsa_gpc", "kaggle/fsa_gpc_transactions/*.csv", vendor=["Merchant Name"],
                           label=["Expense Type"], amount=["Transaction Amount"]),
                   "kaggle", "business", "real", "en", "see MANIFEST"),
    "in_vendor_payments_gl": (_simple("in_vendor_payments_gl", "kaggle/vendor_payments_icai/*.csv",
                                      vendor=["vendor_name"], label=["gl_account_name"], amount=["amount_inr"]),
                              "kaggle", "business", "synthetic", "en", "see MANIFEST"),
    "vynfi_journal_1m": (_vynfi, "huggingface", "business", "synthetic", "en", "see MANIFEST"),
    "uk_bank_business_5class": (_filiptrocin, "transactions", "business", "real", "en", "unclear"),
    # personal finance
    "us_bank_258k": (_simple("us_bank_258k", "transactions/gh_bank-transaction-classification-debertav3/*.csv",
                             desc=["description"], label=["category"], amount=["amount"]),
                     "transactions", "personal", "real", "en", "no licence"),
    "uk_moneydata": (_simple("uk_moneydata", "transactions/mendeley_moneydata/*.xlsx",
                             desc=["Transaction Description"], label=["Category"], amount=["Debit Amount"]),
                     "transactions", "personal", "real", "en", "CC BY 4.0"),
    "bank_categories_50k": (_simple("bank_categories_50k", "huggingface/Dikshith4500__bank-transaction-categories-50k/data/*.parquet",
                                    desc=["text"], label=["category"]),
                            "huggingface", "personal", "synthetic", "en", "see MANIFEST"),
    "us_bank_categories_v2": (_simple("us_bank_categories_v2", "huggingface/DoDataThings__us-bank-transaction-categories-v2/*.csv",
                                      desc=["description"], label=["category"]),
                              "huggingface", "personal", "synthetic", "en", "see MANIFEST"),
    "es_bank_lite": (_simple("es_bank_lite", "huggingface/imbustamante__spanish_bank_transactions_lite/*.parquet",
                             desc=["description"], label=["category"], amount=["amount"]),
                     "huggingface", "personal", "real?", "es", "see MANIFEST"),
    "expense_merchant_desc": (_simple("expense_merchant_desc", "kaggle/expense_categorization_medisumeet/*.csv",
                                      vendor=["merchant"], desc=["description"], label=["category"], amount=["amount"]),
                              "kaggle", "personal", "synthetic", "en", "see MANIFEST"),
    "realistic_spending": (_simple("realistic_spending", "kaggle/realistic_synthetic_spending/*.csv",
                                   vendor=["Merchant"], desc=["Description"], label=["Category"], amount=["Amount"]),
                           "kaggle", "personal", "synthetic", "en", "see MANIFEST"),
}


def load_all(names=None, cap_per_source=200_000, verbose=True) -> pd.DataFrame:
    parts = []
    for name in names or SOURCES:
        loader, group, kind, origin, lang, licence = SOURCES[name]
        try:
            df = loader()
        except Exception as exc:
            if verbose:
                print(f"  skip {name}: {type(exc).__name__}: {str(exc)[:120]}")
            continue
        if df is None or df.empty:
            if verbose:
                print(f"  skip {name}: no rows")
            continue
        if len(df) > cap_per_source:
            df = df.sample(cap_per_source, random_state=0)
        df["source"], df["group"], df["kind"], df["origin"], df["licence"] = name, group, kind, origin, licence
        if "language" not in df:
            df["language"] = lang
        parts.append(df)
        if verbose:
            print(f"  {name:28s} {len(df):>8,} rows")
    out = pd.concat(parts, ignore_index=True)
    out["account"] = out.label_raw.map(map_to_account)
    for c in ("vendor", "description", "label_raw"):
        out[c] = out[c].fillna("").astype(str)
    return out


# ---------------------------------------------------------------------------
# File inventory of data/external (sizes, file types)
# ---------------------------------------------------------------------------
def inventory() -> pd.DataFrame:
    rows = []
    for group_dir in sorted(p for p in EXT.iterdir() if p.is_dir()):
        for ds in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            size, n, kinds = 0, 0, {}
            for f in ds.rglob("*"):
                if f.is_file() and ".git" not in f.parts and ".cache" not in f.parts:
                    size += f.stat().st_size
                    n += 1
                    ext = f.suffix.lower() or "(none)"
                    kinds[ext] = kinds.get(ext, 0) + 1
            rows.append({"group": group_dir.name, "dataset": ds.name, "mb": size / 1e6, "files": n,
                         "top_types": ", ".join(f"{k}:{v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:4]),
                         **{f"n{k}": v for k, v in kinds.items()}})
    return pd.DataFrame(rows).fillna(0)


def cap_per_source(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """At most n random rows from each source."""
    return pd.concat([g.sample(min(len(g), n), random_state=0) for _, g in df.groupby("source")])
