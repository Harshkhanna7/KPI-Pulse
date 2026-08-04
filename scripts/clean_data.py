"""
Data Cleaning & Preparation
Cleans all raw messy sources and produces analysis-ready tables in data/processed/
Also exports an Excel data-quality report.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

def clean_sales():
    df = pd.read_csv(RAW / "online_retail_raw.csv", parse_dates=["InvoiceDate"])
    print(f"[Sales] Raw shape: {df.shape}")

    # Standardise
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Description"] = df["Description"].fillna("UNKNOWN").str.strip().str.upper()
    df["Country"] = df["Country"].str.strip()

    # Flag returns / cancellations
    df["IsReturn"] = (df["Quantity"] < 0) | (df["InvoiceNo"].str.startswith("C"))
    df["QuantityAbs"] = df["Quantity"].abs()
    df["LineRevenue"] = df["Quantity"] * df["UnitPrice"]          # negative for returns
    df["LineRevenueAbs"] = df["QuantityAbs"] * df["UnitPrice"]

    # Remove pure junk (zero price & zero qty, or completely empty)
    before = len(df)
    df = df[~((df["UnitPrice"] == 0) & (df["Quantity"] == 0))]
    df = df[df["UnitPrice"] >= 0]                                 # keep returns (neg qty) but drop neg price
    print(f"[Sales] Dropped {before - len(df)} pure junk rows")

    # CustomerID – keep missing as NaN (important for guest checkout analysis)
    df["CustomerID"] = pd.to_numeric(df["CustomerID"], errors="coerce")

    # Date features
    df["Date"] = df["InvoiceDate"].dt.date
    df["YearWeek"] = df["InvoiceDate"].dt.strftime("%Y-%W")
    df["YearMonth"] = df["InvoiceDate"].dt.to_period("M").astype(str)

    df.to_csv(PROC / "sales_clean.csv", index=False)
    print(f"[Sales] Clean shape: {df.shape} → saved")
    return df

def clean_products():
    df = pd.read_csv(RAW / "products_suppliers_raw.csv")
    print(f"[Products] Raw shape: {df.shape}")

    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Description"] = df["Description"].fillna("UNKNOWN").str.strip().str.upper()

    # Standardise supplier names (simple mapping for demo)
    supplier_map = {
        "ACME SUPPLIES": "Acme Supplies Ltd",
        "acme-supplies": "Acme Supplies Ltd",
        "Global Trade Co.": "GlobalTrade Co",
        "PACIFIC IMPORTERS LLC": "Pacific Importers",
        "Euro Parts": "EuroParts GmbH",
        "Unknown Vendor": "UNKNOWN",
        None: "UNKNOWN"
    }
    df["SupplierClean"] = df["Supplier"].replace(supplier_map).fillna("UNKNOWN")
    df["SupplierClean"] = df["SupplierClean"].str.strip()

    # CostPrice – fix negatives (data entry error)
    df["CostPrice"] = df["CostPrice"].abs()
    df["CostPrice"] = df["CostPrice"].fillna(df["UnitPrice_median"] * 0.55)

    # LeadTime
    df["LeadTimeDays"] = df["LeadTimeDays"].fillna(df["LeadTimeDays"].median())

    # Category standardisation
    cat_map = {"home decor": "Home Decor", "LIGHTING": "Lighting", "Unknown": "Other"}
    df["CategoryClean"] = df["Category"].replace(cat_map).fillna("Other")

    df.to_csv(PROC / "products_clean.csv", index=False)
    print(f"[Products] Clean shape: {df.shape} → saved")
    return df

def clean_inventory():
    df = pd.read_csv(RAW / "inventory_snapshots_raw.csv", parse_dates=["SnapshotDate"])
    print(f"[Inventory] Raw shape: {df.shape}")

    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    # Warehouse name standardisation
    wh_map = {
        "WH-London ": "WH-London",
        "WH_London": "WH-London",
        "Warehouse North": "WH-North",
        "Main": "WH-London"
    }
    df["WarehouseClean"] = df["Warehouse"].replace(wh_map).fillna("UNKNOWN")
    df["OnHandQty"] = pd.to_numeric(df["OnHandQty"], errors="coerce")
    # Flag inconsistencies
    df["IsNegativeStock"] = df["OnHandQty"] < 0
    df["IsMissingQty"] = df["OnHandQty"].isna()

    df.to_csv(PROC / "inventory_clean.csv", index=False)
    print(f"[Inventory] Clean shape: {df.shape} → saved")
    return df

def clean_sessions():
    df = pd.read_csv(RAW / "website_sessions_raw.csv", parse_dates=["Date"])
    print(f"[Sessions] Raw shape: {df.shape}")

    df["Sessions"] = pd.to_numeric(df["Sessions"], errors="coerce")
    df["UniqueVisitors"] = pd.to_numeric(df["UniqueVisitors"], errors="coerce")
    # Forward-fill small gaps for demo (real system would investigate)
    df["Sessions"] = df["Sessions"].ffill().bfill()
    df["UniqueVisitors"] = df["UniqueVisitors"].ffill().bfill()

    ch_map = {"organic": "Organic", "PAID": "Paid Search"}
    df["ChannelClean"] = df["Channel"].replace(ch_map).fillna("Unknown")
    df["DeviceClean"] = df["Device"].str.title().fillna("Unknown")

    df.to_csv(PROC / "sessions_clean.csv", index=False)
    print(f"[Sessions] Clean shape: {df.shape} → saved")
    return df

def clean_returns():
    df = pd.read_csv(RAW / "returns_raw.csv", parse_dates=["InvoiceDate"])
    print(f"[Returns] Raw shape: {df.shape}")

    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    reason_map = {"damaged": "Damaged", "WRONG ITEM": "Wrong Item"}
    df["ReturnReasonClean"] = df["ReturnReason"].replace(reason_map).fillna("Unspecified")
    df["Date"] = df["InvoiceDate"].dt.date

    df.to_csv(PROC / "returns_clean.csv", index=False)
    print(f"[Returns] Clean shape: {df.shape} → saved")
    return df

def data_quality_report(sales, products, inventory, sessions, returns):
    """Write an Excel data-quality summary for stakeholders."""
    with pd.ExcelWriter(ROOT / "exports" / "Data_Quality_Report.xlsx", engine="xlsxwriter") as writer:
        # Sales summary
        s_sum = pd.DataFrame({
            "Metric": ["Total Rows", "Date Range", "Unique Invoices", "Unique SKUs",
                       "Returns (neg qty)", "Missing CustomerID %", "Missing Description %"],
            "Value": [
                len(sales),
                f"{sales['InvoiceDate'].min().date()} → {sales['InvoiceDate'].max().date()}",
                sales["InvoiceNo"].nunique(),
                sales["StockCode"].nunique(),
                sales["IsReturn"].sum(),
                round(sales["CustomerID"].isna().mean()*100, 1),
                round((sales["Description"]=="UNKNOWN").mean()*100, 1)
            ]
        })
        s_sum.to_excel(writer, sheet_name="Sales_DQ", index=False)

        # Inventory DQ
        inv_sum = pd.DataFrame({
            "Metric": ["Snapshots", "Negative Stock Rows", "Missing Qty Rows", "Unique Warehouses (raw)"],
            "Value": [len(inventory), inventory["IsNegativeStock"].sum(),
                      inventory["IsMissingQty"].sum(), inventory["Warehouse"].nunique()]
        })
        inv_sum.to_excel(writer, sheet_name="Inventory_DQ", index=False)

        # Supplier name drift
        prod_sum = products.groupby("SupplierClean").size().reset_index(name="SKU_Count")
        prod_sum.to_excel(writer, sheet_name="Supplier_Standardisation", index=False)

        # Returns reasons
        returns["ReturnReasonClean"].value_counts().to_frame("Count").to_excel(
            writer, sheet_name="Return_Reasons")

    print("[DQ] Excel report written → exports/Data_Quality_Report.xlsx")

if __name__ == "__main__":
    sales = clean_sales()
    products = clean_products()
    inventory = clean_inventory()
    sessions = clean_sessions()
    returns = clean_returns()
    data_quality_report(sales, products, inventory, sessions, returns)
    print("\n✅ Phase 03 complete – cleaned data in data/processed/")
